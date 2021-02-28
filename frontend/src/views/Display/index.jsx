import React, { useEffect, useState } from 'react';
import { useSelector, useDispatch } from 'react-redux';

import Grid from '@material-ui/core/Grid';
import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';

import { loadDisplayInfo, setDisplayEffect, clearDisplayEffect } from 'modules/selectedDisplay';
import { activatePreset, getEffectPresets, addPreset } from 'modules/presets';
import DisplayEffectControl from 'components/EffectControl/DisplayEffectControl';
import BladeDisplayEffectControl from 'components/EffectControl/BladeDisplayEffectControl';
import DisplayPixelColorGraph from 'components/PixelColorGraph/DisplayPixelColorGraph';
import PixelColorGraph from 'components/PixelColorGraph';
import PresetsCard from 'components/PresetsCard';
import TransitionCard from 'components/TransitionCard';
import { fetchDisplayList } from 'modules/displays';
import { fetchDeviceList } from 'modules/devices';
import MoreInfo from './MoreInfo';

const DisplayView = ({
    match: {
        params: { displayId },
    },
}) => {
    const schemas = useSelector(state => state.schemas);
    const selectedDisplay = useSelector(state => state.selectedDisplay);
    const { display, effect, isDisplayLoading } = selectedDisplay;
    const presets = useSelector(state => state.presets);
    const devices = useSelector(state => state.devices.list);
    const deviceId = display && display.config[display.id].is_device;
    const device = devices.find(d => d.id === deviceId);
    const dispatch = useDispatch();
    const [dispId, setDispId] = useState();

    useEffect(() => {
        if (displayId !== dispId) {
            dispatch(loadDisplayInfo(displayId));
            setDispId(displayId);
        }
    }, [displayId, dispId, dispatch]);

    useEffect(() => {
        dispatch(fetchDisplayList());
        dispatch(fetchDeviceList());
    }, [dispatch]);

    if (schemas.isLoading || isDisplayLoading || !display) {
        return <p>Loading...</p>;
    }
    return (
        <>
            <Grid container direction="row" spacing={4}>
                {renderPixelGraph(display, effect, device)}
                <Grid item xs={12} lg={6}>

                    {parseInt(window.localStorage.getItem('BladeMod')) > 2 ? (
                        <Card>
                            <CardContent>
                                <BladeDisplayEffectControl
                                    display={display}
                                    effect={effect}
                                    schemas={schemas}
                                    onClear={() => dispatch(clearDisplayEffect(displayId))}
                                    onSubmit={data => dispatch(setDisplayEffect(data.displayId, data))}
                                    onTypeChange={effectType =>
                                        effectType ? dispatch(getEffectPresets(effectType)) : false
                                    }
                                />
                            </CardContent>
                        </Card>) : (
                            <Card>
                                <CardContent>
                                    <DisplayEffectControl
                                        display={display}
                                        effect={effect}
                                        schemas={schemas}
                                        onClear={() => dispatch(clearDisplayEffect(displayId))}
                                        onSubmit={data => dispatch(setDisplayEffect(data.displayId, data))}
                                        onTypeChange={effectType =>
                                            effectType ? dispatch(getEffectPresets(effectType)) : false
                                        }
                                    />
                                </CardContent>
                            </Card>
                        )}
                </Grid>
                <Grid item xs={12} lg={6}>
                    {effect.type && (
                        <PresetsCard
                            display={display}
                            presets={presets}
                            effect={effect}
                            activatePreset={() => dispatch(activatePreset)}
                            getEffectPresets={() => dispatch(getEffectPresets)}
                            addPreset={() => dispatch(addPreset)}
                        />
                    )}
                    {parseInt(window.localStorage.getItem('BladeMod')) > 1 && (
                        <TransitionCard
                            display={display}
                        />
                    )}
                </Grid>
                {parseInt(window.localStorage.getItem('BladeMod')) > 1 && (
                    <MoreInfo display={display} />
                )}
            </Grid>
        </>
    );
};

const renderPixelGraph = (display, effect, device) => (
    <Grid item xs={12}>
        <Card>
            <CardContent className={`effect-${!!effect}`}>
                {display && device ? (
                    <PixelColorGraph device={device} />
                ) : display && !device ? (
                    <DisplayPixelColorGraph display={display} />
                ) : (
                            <></>
                        )}
            </CardContent>
        </Card>
    </Grid>
);

export default DisplayView;
