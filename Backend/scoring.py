"""
    Scores every pick for a finished game from its stored box score.

    Lives outside the routers because two callers need it: the admin endpoint now
    (POST /api/admin/games/{game_id}/score), and the step 11 poller later, which calls it
    the moment a game goes final. So it raises ScoringError rather than an HTTPException,
    and the caller decides what that means for it.

    Safe to run twice: a scored game is skipped unless force is passed, and a forced rescore
    overwrites points rather than adding to them. Everything is written in one commit.
"""
from datetime import datetime, UTC

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import models
from config import settings
from schemas import CategoryKind, GameScoreResponse, GameStatus

# margin of victory partial credit (decided: the wider tiers). off by at most N points earns that many
# thirds of the category's points, rounded down, so the default 3 points pays 3 / 2 / 1 / 0, and the
# tiers scale if an admin reweights the category
MARGIN_TIERS = [(0, 3), (5, 2), (10, 1)] # (most points off, thirds of the category's points)


class ScoringError(Exception):
    """The game can't be scored yet. The message says why."""


def margin_points(picked: int, actual: int, points: int) -> int:
    off = abs(picked - actual)
    for most_off, thirds in MARGIN_TIERS:
        if off <= most_off:
            return points * thirds // 3
    return 0


def stat_leaders(lines: list[models.PlayerGameStat], stat: str) -> set[int]:
    """Player ids tied for the lead in a stat among the players who appeared.

    Ties all count as the leader: in the season opener three Raptors scored 23, and picking any
    of them was right. If nobody recorded the stat at all (no Raptor had a steal), nobody leads it.
    """
    played = [line for line in lines if line.minutes is not None] # a DNP line has no minutes and leads nothing
    best = max((getattr(line, stat) for line in played), default=0)
    if best == 0:
        return set()
    return {line.player_id for line in played if getattr(line, stat) == best}


async def score_game(db: AsyncSession, game: models.Game, force: bool = False) -> GameScoreResponse:
    """`game` must have home_team and away_team loaded."""
    if game.status != GameStatus.FINAL:
        raise ScoringError("Only a final game can be scored")
    if game.home_score is None or game.away_score is None:
        raise ScoringError("This game has no final score")

    lines = (await db.execute(
        select(models.PlayerGameStat)
        .options(selectinload(models.PlayerGameStat.player))
        .where(models.PlayerGameStat.game_id == game.game_id),
    )).scalars().all()
    if not lines:
        raise ScoringError("No box score for this game yet")

    # leaders are found among the Raptors who played, by the team on the box score line (a player
    # traded since still counts for the side he played for that night)
    followed_id = (await db.execute(
        select(models.Team.team_id).where(models.Team.tricode == settings.team_tricode),
    )).scalar_one_or_none()
    our_lines = [line for line in lines if line.team_id == followed_id]
    names = {line.player_id: line.player.full_name for line in lines}

    home_won = game.home_score > game.away_score # an nba game can't end tied
    winner_id = game.home_team_id if home_won else game.away_team_id
    winner = (game.home_team if home_won else game.away_team).tricode
    margin = abs(game.home_score - game.away_score)

    # inactive categories included: a pick made before an admin deactivated its category still counts
    categories = {c.pick_category_id: c for c in (await db.execute(select(models.PickCategory))).scalars()}
    leaders = {
        c.key: stat_leaders(our_lines, c.stat)
        for c in categories.values() if c.kind == CategoryKind.STAT_LEADER
    }
    leader_names = {key: sorted(names[player_id] for player_id in ids) for key, ids in leaders.items()}

    if game.scored_at is not None and not force:
        return GameScoreResponse(
            game_id=game.game_id, scored=False, scored_at=game.scored_at, winner=winner,
            margin=margin, leaders=leader_names, picks_scored=0,
        )

    picks = (await db.execute(select(models.Pick).where(models.Pick.game_id == game.game_id))).scalars().all()

    # a margin pick reads as "TOR by 8", so it only counts for users whose winner pick was right (decided)
    right_winner = {
        pick.user_id for pick in picks
        if categories[pick.pick_category_id].kind == CategoryKind.WINNER and pick.team_id == winner_id
    }

    for pick in picks:
        category = categories[pick.pick_category_id]
        kind = CategoryKind(category.kind)
        if kind == CategoryKind.WINNER:
            points = category.points if pick.team_id == winner_id else 0
        elif kind == CategoryKind.MARGIN:
            points = margin_points(pick.margin, margin, category.points) if pick.user_id in right_winner else 0
        else:
            points = category.points if pick.player_id in leaders[category.key] else 0
        # written, not added: a forced rescore after a stat correction replaces the old result
        pick.points_awarded = points

    game.scored_at = datetime.now(UTC)
    await db.commit()

    return GameScoreResponse(
        game_id=game.game_id, scored=True, scored_at=game.scored_at, winner=winner,
        margin=margin, leaders=leader_names, picks_scored=len(picks),
    )
