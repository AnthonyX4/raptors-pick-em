// the team this app follows. mirrors the backend's settings.team_tricode, which the api doesn't expose:
// change both together. it picks the roster that stat leader picks are chosen from
export const FOLLOWED_TEAM = "TOR"

// the longest chat message, mirroring the backend's message_max_length (500): the api still checks it
export const MESSAGE_MAX_LENGTH = 500
