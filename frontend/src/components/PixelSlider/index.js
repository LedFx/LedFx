import React from 'react'
import Slider from '@material-ui/core/Slider';

const PixelSlider = ({ pixel_count, setconfig, config, yz, listItem, totalPixel, settotalPixel }) => {
    const [value, setValue] = React.useState([0, pixel_count]);
    const handleChange = (event, newValue) => {


        // console.log(newValue[0], config.led_start, " und ", newValue[1], config.led_end)


        setValue(newValue);
        const test = config
        test[`${yz}`] = { led_start: newValue[0], led_end: newValue[1] }
        setconfig(test)
        console.log("CONFIG: ", config)

        // if ((newValue[0] !== config[yz].led_start) || (newValue[1] !== config[yz].led_end)) {

        //     setValue(newValue);
        //     const test = config
        //     test[`${yz}`] = { led_start: newValue[0], led_end: newValue[1], pixels: newValue[1] - newValue[0], listItem }
        //     setconfig(test)
        //     console.log(config)

    }


    const marks =
        [
            {
                value: 0,
                label: 0,
            },
            {
                value: pixel_count,
                label: pixel_count,
            },
        ];

    return (
        <Slider
            value={value}
            marks={marks}
            min={0}
            max={pixel_count}
            onChange={handleChange}
            aria-labelledby="range-slider"
            valueLabelDisplay="on"
        />
    )
}

export default PixelSlider
