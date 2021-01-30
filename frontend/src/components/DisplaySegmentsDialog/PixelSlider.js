import React, { useEffect } from 'react';
import Slider from '@material-ui/core/Slider';
import { useDispatch, useSelector } from 'react-redux';
import { fetchDeviceList } from 'modules/devices';
import { handleSegmentChange } from 'modules/displays';
const PixelSlider = ({ s, i, display }) => {
    const dispatch = useDispatch();
    const devices = useSelector(state => state.devices.list);
    useEffect(() => {
        dispatch(fetchDeviceList);
    }, [dispatch]);

    const currentDevice = devices.find(reduxItem => reduxItem.id === s[0]);
    if (!currentDevice) {
        return <></>;
    }
    const pixelRange = [s[1], s[2]];

    const handleChange = (event, newValue) => {
        if (newValue !== pixelRange) {
            dispatch(handleSegmentChange({ newValue, displayId: display.id, segIndex: i }));
        }
    };

    const marks = [
        { value: 0, label: 0 },
        {
            value: currentDevice.config.pixel_count - 1,
            label: currentDevice.config.pixel_count - 1,
        },
    ];

    return (
        <Slider
            value={pixelRange}
            marks={marks}
            min={0}
            max={currentDevice.config.pixel_count - 1}
            onChange={handleChange}
            aria-labelledby="range-slider"
            valueLabelDisplay="auto"
        />
    );
};

export default PixelSlider;
