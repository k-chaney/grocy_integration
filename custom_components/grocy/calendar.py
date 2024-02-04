"""Todo platform for Grocy."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import datetime
import logging
from typing import Any

from pygrocy.data_models.battery import Battery
from pygrocy.data_models.chore import Chore
from pygrocy.data_models.product import Product
from pygrocy.data_models.task import Task

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import DEFAULT_TIME_ZONE, now

from .const import (
    ATTR_BATTERIES,
    ATTR_CHORES,
    ATTR_EXPIRING_PRODUCTS,
    ATTR_MEAL_PLAN,
    ATTR_TASKS,
    DOMAIN,
)
from .coordinator import GrocyCoordinatorData, GrocyDataUpdateCoordinator
from .entity import GrocyEntity
from .helpers import MealPlanItemWrapper

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Do setup todo platform."""
    coordinator: GrocyDataUpdateCoordinator = hass.data[DOMAIN]
    entities = []
    for description in CALENDARS:
        if description.exists_fn(coordinator.available_entities):
            entity = GrocyCalendarEntity(coordinator, description, config_entry)
            coordinator.entities.append(entity)
            entities.append(entity)
        else:
            _LOGGER.debug(
                "Entity description '%s' is not available",
                description.key,
            )

    async_add_entities(entities, True)


@dataclass
class GrocyCalendarEntityDescription(EntityDescription):
    """Grocy todo entity description."""

    attributes_fn: Callable[[list[Any]], GrocyCoordinatorData | None] = lambda _: None
    exists_fn: Callable[[list[str]], bool] = lambda _: True
    entity_registry_enabled_default: bool = False


CALENDARS: tuple[GrocyCalendarEntityDescription, ...] = (
    GrocyCalendarEntityDescription(
        key=ATTR_BATTERIES,
        name="Grocy batteries",
        icon="mdi:battery",
        exists_fn=lambda entities: ATTR_BATTERIES in entities,
    ),
    GrocyCalendarEntityDescription(
        key=ATTR_CHORES,
        name="Grocy chores",
        icon="mdi:broom",
        exists_fn=lambda entities: ATTR_CHORES in entities,
    ),
    GrocyCalendarEntityDescription(
        key=ATTR_EXPIRING_PRODUCTS,
        name="Grocy expiring products",
        icon="mdi:clock-fast",
        exists_fn=lambda entities: ATTR_EXPIRING_PRODUCTS in entities,
    ),
    GrocyCalendarEntityDescription(
        key=ATTR_MEAL_PLAN,
        name="Grocy meal plan",
        icon="mdi:silverware-variant",
        exists_fn=lambda entities: ATTR_MEAL_PLAN in entities,
    ),
    GrocyCalendarEntityDescription(
        key=ATTR_TASKS,
        name="Grocy tasks",
        icon="mdi:checkbox-marked-circle-outline",
        exists_fn=lambda entities: ATTR_TASKS in entities,
    ),
)


class GrocyCalendarEvent(CalendarEvent):  # noqa: D101
    def __init__(  # noqa: D107
        self,
        item: Chore | Battery | MealPlanItemWrapper | Product | Task | None = None,
        key: str = "",
    ) -> None:
        if isinstance(item, Chore):
            end = (
                item.next_estimated_execution_time.replace(tzinfo=DEFAULT_TIME_ZONE)
                if item.next_estimated_execution_time
                else now()
            )
            # Chores have a due time, but no start time, designate an hour before start time
            start = end - datetime.timedelta(hours=1)
            super().__init__(
                uid=item.id.__str__(),
                summary=item.name,
                start=start,
                end=end,
                description=item.description or None,
                location=None,
                recurrence_id=None,
                rrule=None,
            )
        elif isinstance(item, Battery):
            end = (
                item.next_estimated_charge_time.replace(tzinfo=DEFAULT_TIME_ZONE)
                if item.next_estimated_charge_time
                else now()
            )
            # Batteries have a due time, but no start time, designate an hour before start time
            start = end - datetime.timedelta(hours=1)
            super().__init__(
                uid=item.id.__str__(),
                summary=item.name,
                start=start,
                end=end,
                description=item.description or None,
                location=None,
                recurrence_id=None,
                rrule=None,
            )
        elif isinstance(item, MealPlanItemWrapper):
            start = item.meal_plan.day if item.meal_plan.day else now().date()
            # Meal Plans have a due time, but no start time, designate an hour before start time
            end: datetime.date = start + datetime.timedelta(days=1)
            super().__init__(
                uid=item.meal_plan.id.__str__(),
                summary=item.meal_plan.recipe.name,
                start=start,
                end=end,
                description=item.meal_plan.recipe.description or None,
                location=None,
                recurrence_id=None,
                rrule=None,
            )
        elif isinstance(item, Product):
            start = item.best_before_date if item.best_before_date else now().date()
            # Meal Plans have a due time, but no start time, designate an hour before start time
            end: datetime.date = start + datetime.timedelta(days=1)
            super().__init__(
                uid=item.id.__str__(),
                summary=item.name,
                start=start,
                end=end,
                description=None,
                location=None,
                recurrence_id=None,
                rrule=None,
            )
        elif isinstance(item, Task):
            start = item.due_date if item.due_date else now().date()
            # end.tzinfo = datetime.UTC
            # Tasks have a due time, but no start time, designate an hour before start time
            end = start + datetime.timedelta(days=1)
            super().__init__(
                uid=item.id.__str__(),
                summary=item.name,
                start=start,
                end=end,
                description=item.description or None,
                location=None,
                recurrence_id=None,
                rrule=None,
            )
        else:
            raise NotImplementedError(f"{key} => {type(item)}")


class GrocyCalendarEntity(GrocyEntity, CalendarEntity):
    """Grocy calendar entity definition."""

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""

        return None
        # entities = self.coordinator.data[self.entity_description.key]
        # if entities is None or len(entities) < 1:
        #     return None

        # entity = entities[0]
        # if entity is None:
        #     return None

        # return GrocyCalendarEvent(entity) if entity is not None else None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
    ) -> list[CalendarEvent] | None:
        """Return the value reported by the todo."""
        entity_data = self.coordinator.data[self.entity_description.key]
        return (
            [
                GrocyCalendarEvent(item, self.entity_description.key)
                for item in entity_data
                if item is not None
            ]
            if entity_data
            else []
        )
