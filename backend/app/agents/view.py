"""A character's subjective view of the world, built from its beliefs.

Planners read the world only through this view. The static map layout (which locations a
route joins, its length, its ability requirement) is common knowledge; everything that can
change - route status, obstructions, traps, item locations - comes from the character's beliefs.
"""

from app.engine.movement import find_path_on, route_seconds
from app.models.actions import ProposedAction
from app.models.enums import ActionType
from app.models.mind import ObjectBelief, RouteBelief
from app.models.world import Route, WorldState


class BeliefView:
    def __init__(self, world: WorldState, character_id: str):
        self.world = world
        self.cid = character_id
        self.mind = world.minds[character_id]
        self.beliefs = self.mind.beliefs
        self.profile = world.profiles[character_id]
        self.here = world.characters[character_id].location_id
        self.now = world.clock.now
        self._routes = [self._believed(r) for r in world.routes.values()]

    def _believed(self, route: Route) -> Route:
        rb = self.beliefs.routes[route.id]
        return route.model_copy(update={
            "hidden": not rb.known,
            "status": rb.status,
            "obstructed": rb.obstructed,
            "hazard_active": rb.hazard_active,
        })

    # --- map -----------------------------------------------------------------------------------

    def route(self, route_id: str) -> RouteBelief:
        return self.beliefs.routes[route_id]

    def path(self, goal: str, start: str | None = None) -> list[Route] | None:
        origin = start or self.here
        if origin is None:
            return None
        return find_path_on(self._routes, self.profile, origin, goal)

    def eta(self, goal: str, start: str | None = None) -> int | None:
        p = self.path(goal, start)
        return None if p is None else sum(route_seconds(self.profile, r) for r in p)

    def route_time(self, route_id: str) -> int:
        return route_seconds(self.profile, next(r for r in self._routes if r.id == route_id))

    def next_hop(self, goal: str) -> ProposedAction | None:
        p = self.path(goal)
        if not p or self.here is None:
            return None
        return ProposedAction(actor=self.cid, type=ActionType.MOVE, destination=p[0].other_end(self.here),
                              route_id=p[0].id)

    # --- things and people ---------------------------------------------------------------------

    def carrying(self, object_id: str) -> bool:
        return self.world.carries(self.cid, object_id)  # one's own pockets are always known

    def item(self, object_id: str) -> ObjectBelief:
        return self.beliefs.objects.get(object_id, ObjectBelief())

    def last_seen(self, character_id: str) -> str | None:
        cb = self.beliefs.characters.get(character_id)
        return cb.location_id if cb else None

    def action(self, type: ActionType, **kw) -> ProposedAction:
        return ProposedAction(actor=self.cid, type=type, **kw)
