package io.datagov.server.event;

import io.datagov.common.dto.EventDtos;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api")
public class EventController {
    private final EventService eventService;

    public EventController(EventService eventService) {
        this.eventService = eventService;
    }

    @PostMapping("/assets/{assetCode}/events")
    public EventDtos.CreateAssetEventResponse createEvent(
            @PathVariable("assetCode") String assetCode,
            @Valid @RequestBody EventDtos.CreateAssetEventRequest request
    ) {
        return eventService.createEvent(assetCode, request);
    }
}
