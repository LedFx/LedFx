# Architecture notes

The following are generated via AI assisted spelunking, but are then hand curated for relevance.

## LedFx runtime flow

```{mermaid}
sequenceDiagram
    autonumber
    participant Core as LedFxCore
    participant Config as Config Loader
    participant API as HTTP/API Server
    participant Audio as Audio Manager
    participant Virtuals as Virtual Manager
    participant Effects as Effect Engine
    participant Segments as Segment Mapper
    participant Devices as Physical Devices

    Core->>Config: Load configuration
    Core->>Virtuals: Initialize virtuals
    Core->>Effects: Initialize effects
    Core->>Devices: Initialize output devices
    Core->>Audio: Start audio input stream
    Core->>API: Start API and Web UI

    loop Runtime Frame (~60 FPS)
        Audio->>Audio: Process incoming audio frame
        Audio-->>Effects: Audio state (FFT, volume, beats)

        Core->>Virtuals: Get each active virtual
        Virtuals->>Effects: Generate effect
        Effects-->>Virtuals: Return pixel array

        Virtuals->>Segments: Apply mapping (span/copy/grouping)
        Segments->>Devices: Pixel data to device
        Devices->>Devices: Flush frame to hardware
    end
```