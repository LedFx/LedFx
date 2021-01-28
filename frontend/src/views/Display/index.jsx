import React, { useEffect, useState } from 'react';
import { useSelector, useDispatch } from 'react-redux';

import Grid from '@material-ui/core/Grid';
import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';

import { loadDisplayInfo, setDisplayEffect, clearDisplayEffect } from 'modules/selectedDisplay';
import { activatePreset, getEffectPresets, addPreset } from 'modules/presets';
import DisplayEffectControl from 'components/EffectControl/DisplayEffectControl';
import DisplayPixelColorGraph from 'components/PixelColorGraph/DisplayPixelColorGraph';
import PresetsCard from 'components/PresetsCard';
import { fetchDisplayList } from 'modules/displays';
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
    }, [dispatch]);

    if (schemas.isLoading || isDisplayLoading || !display) {
        return <p>Loading...</p>;
    }

    return (
        <>
            <Grid container direction="row" spacing={4}>
                {Object.keys(effect).length === 0 ? (
                    <Grid item xs={12} lg={12}>
                        <Card>
                            <CardContent>
                                <DisplayPixelColorGraph display={display} />
                            </CardContent>
                        </Card>
                    </Grid>
                ) : (
                    renderPixelGraph(display, effect)
                )}

                <Grid item xs={12} lg={6}>
                    <Card>
                        <CardContent>
                            <DisplayEffectControl
                                display={display}
                                effect={effect}
                                schemas={schemas}
                                onClear={() => dispatch(clearDisplayEffect(displayId))}
                                onSubmit={data => dispatch(setDisplayEffect(data.displayId, data))}
                                onTypeChange={effectType => dispatch(getEffectPresets(effectType))}
                            />
                        </CardContent>
                    </Card>
                </Grid>
                <Grid item xs={12} lg={6}>
                    {effect.type && (
                        <PresetsCard
                            device={display}
                            presets={presets}
                            effect={effect}
                            activatePreset={() => dispatch(activatePreset)}
                            getEffectPresets={() => dispatch(getEffectPresets)}
                            addPreset={() => dispatch(addPreset)}
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

const renderPixelGraph = (display, effect) => {
    if (display && effect?.name) {
        return (
            <Grid item xs={12}>
                <Card>
                    <CardContent>
                        <DisplayPixelColorGraph display={display} />
                    </CardContent>
                </Card>
            </Grid>
        );
    }
};

export default DisplayView;
