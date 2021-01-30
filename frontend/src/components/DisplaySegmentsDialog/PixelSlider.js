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
    // console.log(devices);
    if (!currentDevice) {
        return <></>;
    }
    const pixelRange = [s[1], s[2]];

    const handleChange = (event, newValue) => {
        console.log(newValue, display, i);
        if (newValue !== pixelRange) {
            dispatch(handleSegmentChange({ newValue, displayId: display.id, segIndex: i }));
            // dispatch({
            //     type: 'virtuals/CHANGE_SEGMENT_PXEL',
            //     payload: { virtual: virtual, device: device.id, newValue: newValue },
            // });
        }
    };

    const marks = [
        { value: 1, label: 1 },
        { value: currentDevice.config.pixel_count, label: currentDevice.config.pixel_count },
    ];

    return (
        <Slider
            value={pixelRange}
            marks={marks}
            min={1}
            max={currentDevice.config.pixel_count}
            onChange={handleChange}
            aria-labelledby="range-slider"
            valueLabelDisplay="auto"
            style={{ flex: '0 0 50%' }}
        />
    );
};

export default PixelSlider;
