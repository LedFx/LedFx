#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import pytest
import numpy as np
from ledfx.devices import DeviceManager
from ledfx.effects.rainbow import RainbowEffect
from ledfx.effects.spectrum import SpectrumAudioEffect
from ledfx.effects.wavelength import WavelengthAudioEffect
from ledfx.effects.gradient import TemporalGradientEffect
from ledfx.effects import Effect, EffectManager

# TODO: Cleanup test as they are not 100% functional yet

# BASIC_E131_CONFIG = {
#     "name": "Test E131 Device",
#     "e131":
#     {
#         "host": "192.168.1.185",
#         "channel_count": 96
#     }
# }

BASIC_E131_CONFIG = {
    "name": "Test E131 Device",
    "e131":
    {
        "host": "192.168.1.183",
        "channel_count": 900
    }
}

# def test_device_creation():
#     deviceManager = DeviceManager()
    
#     device = deviceManager.createDevice(BASIC_E131_CONFIG)
#     assert device is not None

# def test_device_channel():
#     deviceManager = DeviceManager()
#     device = deviceManager.createDevice(BASIC_E131_CONFIG)

#     assert device.outputChannels[0].pixelCount == 32
#     assert len(device.outputChannels[0].pixels) == 32

#     # Validate setting the pixels as a single tuple
#     device.outputChannels[0].pixels = (255, 0, 0)
#     for pixel in range(0, device.outputChannels[0].pixelCount):
#         assert (device.outputChannels[0].pixels[pixel] == (255, 0, 0)).all()
    
#     # Validate the output channel gets assembled into the frame
#     frame = device.assembleFrame()
#     for pixel in range(0, device.outputChannels[0].pixelCount):
#         assert (frame[pixel] == (255, 0, 0)).all()

#     # Validate setting the pixels as a numpy array of equal size
#     device.outputChannels[0].pixels = np.zeros((device.outputChannels[0].pixelCount, 3))
#     for pixel in range(0, device.outputChannels[0].pixelCount):
#         assert (device.outputChannels[0].pixels[pixel] == (0, 0, 0)).all()
    
#     # Validate the output channel gets assembled into the frame
#     frame = device.assembleFrame()
#     for pixel in range(0, device.outputChannels[0].pixelCount):
#         assert (frame[pixel] == (0, 0, 0)).all()

# def test_effect_rainbow():
#     deviceManager = DeviceManager()
#     device = deviceManager.createDevice(BASIC_E131_CONFIG)
#     assert device is not None

#     effectManager = EffectManager()
#     effect = effectManager.createEffect("Rainbow")
#     assert effect is not None

#     device.activate()
#     effect.activate(device.outputChannels[0])

#     time.sleep(5) # Default
#     effect.updateConfig({'speed': 3.0})
#     time.sleep(5) # Default w/ 3x speed
#     effect.updateConfig({'frequency': 3.0})
#     time.sleep(5) # Default w/ 3x frequency

#     effect.deactivate()
#     device.deactivate()

# def test_effect_gradient_shift():
#     deviceManager = DeviceManager()
#     device = deviceManager.createDevice(BASIC_E131_CONFIG)
#     assert device is not None

#     effectManager = EffectManager()
#     effect = effectManager.createEffect("Gradient", { "gradient": "Dancefloor"})
#     assert effect is not None

#     device.activate()
#     effect.activate(device.outputChannels[0])

#     time.sleep(5)

#     effect.deactivate()
#     device.deactivate()

#     assert False

# def test_effect_spectrum():
#     deviceManager = DeviceManager()
#     device = deviceManager.createDevice(BASIC_E131_CONFIG)
#     assert device is not None

#     effectManager = EffectManager()
#     effect = effectManager.createEffect("Spectrum")
#     assert effect is not None

#     device.activate()
#     effect.activate(device.outputChannels[0])

#     time.sleep(20)

#     effect.deactivate()
#     device.deactivate()

#     assert False
