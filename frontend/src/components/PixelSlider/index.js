import React from 'react'
import Slider from '@material-ui/core/Slider';

const PixelSlider = ({ pixel_count, setconfig, config, yz }) => {
    const [value, setValue] = React.useState([0, pixel_count]);

    const handleChange = (event, newValue) => {
        if (newValue !== value) {
            setValue(newValue);
            const test = { ...config }
            test[`${yz}`] = { led_start: newValue[0], led_end: newValue[1] }
            setconfig(test)
        }
    }

    const marks =
        [
            { value: 0, label: 0, },
            { value: pixel_count, label: pixel_count, },
        ];

    return (
        <Slider
            value={value}
            marks={marks}
            min={0}
            max={pixel_count}
            onChange={handleChange}
            aria-labelledby="range-slider"
            valueLabelDisplay="auto"
            style={{ marginBottom: "15px" }}
        />
    )
}

export default PixelSlider
