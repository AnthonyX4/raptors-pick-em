import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import type { GameDetail, PlayerStat, Team } from "../api"

function TeamTable({ team, stats }: { team: Team; stats: PlayerStat[] }) {
  return (
    <div>
      <h3 className="mb-2 font-display text-2xl font-bold tracking-wide uppercase">{team.full_name}</h3>
      <div className="rounded-md border border-border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Player</TableHead>
              <TableHead className="text-right">Min</TableHead>
              <TableHead className="text-right">Pts</TableHead>
              <TableHead className="text-right">Reb</TableHead>
              <TableHead className="text-right">Ast</TableHead>
              <TableHead className="text-right">Stl</TableHead>
              <TableHead className="text-right">Blk</TableHead>
              <TableHead className="text-right">TO</TableHead>
              <TableHead className="text-right">3PM</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {stats.map((stat) =>
              // minutes is null for a player who didn't appear: show why instead of a row of zeros
              stat.minutes === null ? (
                <TableRow key={stat.player.player_id} className="text-muted-foreground">
                  <TableCell>{stat.player.full_name}</TableCell>
                  <TableCell colSpan={8} className="text-right">
                    {stat.comment || "Did not play"}
                  </TableCell>
                </TableRow>
              ) : (
                <TableRow key={stat.player.player_id} className="tabular-nums">
                  <TableCell className="font-medium">{stat.player.full_name}</TableCell>
                  <TableCell className="text-right text-muted-foreground">{stat.minutes}</TableCell>
                  <TableCell className="text-right font-bold">{stat.points}</TableCell>
                  <TableCell className="text-right">{stat.rebounds_total}</TableCell>
                  <TableCell className="text-right">{stat.assists}</TableCell>
                  <TableCell className="text-right">{stat.steals}</TableCell>
                  <TableCell className="text-right">{stat.blocks}</TableCell>
                  <TableCell className="text-right">{stat.turnovers}</TableCell>
                  <TableCell className="text-right">{stat.three_pointers_made}</TableCell>
                </TableRow>
              ),
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}

export function BoxScore({ game }: { game: GameDetail }) {
  if (game.player_stats.length === 0) {
    // the poller fetches the box score after the final buzzer, so a finished game can be without one briefly
    if (game.status !== "final") return null
    return <p className="text-sm text-muted-foreground">The box score will appear shortly.</p>
  }

  // the api sends the highest scorer first, which each team's table keeps
  const forTeam = (team: Team) => game.player_stats.filter((stat) => stat.team_id === team.team_id)

  return (
    <section className="space-y-8">
      <h2 className="font-display text-3xl font-bold tracking-wide uppercase">Box score</h2>
      <TeamTable team={game.away_team} stats={forTeam(game.away_team)} />
      <TeamTable team={game.home_team} stats={forTeam(game.home_team)} />
    </section>
  )
}
