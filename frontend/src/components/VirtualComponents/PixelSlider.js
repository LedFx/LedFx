import React from 'react'
import Slider from '@material-ui/core/Slider';
import { useDispatch, useSelector } from "react-redux";

const PixelSlider = ({ virtual, device }) => {
    const dispatch = useDispatch();
    const virtualsList = useSelector(state => state.virtuals.list)
    const currentVirtual = virtualsList.find(reduxItem => reduxItem.name === virtual).items.find(d => d.id === device.id)
    if (!currentVirtual) {
        return <></>
    }
    const pixelRange = [currentVirtual.led_start, currentVirtual.led_end]

    const handleChange = (event, newValue) => {
        if (newValue !== pixelRange) {
            dispatch({ type: 'virtuals/CHANGE_SEGMENT', payload: { virtual: virtual, device: device.id, newValue: newValue } })
        }
    }

    const marks =
        [
            { value: 1, label: 1, },
            { value: currentVirtual.config.pixel_count, label: currentVirtual.config.pixel_count, },
        ];

    return (
        <Slider
            value={pixelRange}
            marks={marks}
            min={1}
            max={currentVirtual.config.pixel_count}
            onChange={handleChange}
            aria-labelledby="range-slider"
            valueLabelDisplay="auto"
            style={{ marginBottom: "15px" }}
        />
    )
}

export default PixelSlider
