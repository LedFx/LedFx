import React from 'react';
import PropTypes from 'prop-types';
import { connect } from 'react-redux';

import Grid from '@material-ui/core/Grid';
import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
import Typography from '@material-ui/core/Typography';

import { loadDisplayInfo, setDisplayEffect, clearDisplayEffect } from 'modules/selectedDisplay';
import { activatePreset, getEffectPresets, addPreset } from 'modules/presets';
import DisplayEffectControl from 'components/EffectControl/DisplayEffectControl';
// import EffectControlBlade from 'components/EffectControl/blade';
import DisplayPixelColorGraph from 'components/PixelColorGraph/DisplayPixelColorGraph';
import PresetsCard from 'components/PresetsCard';
import { fetchDisplayList } from 'modules/displays';


const DisplayView = ({match: {params}, presets, schemas, selectedDisplay, addPreset, activatePreset, clearDisplayEffect, loadDisplayInfo, setDisplayEffect, getEffectPresets}) => {
    const [state, setState] = useState();
    useEffect(() => {
        fetchDisplayList();
        setState(params);
    }, []);
    useEffect(() => {
        if(params !== state){
            handleLoadDisplay(params);
            setState(params);
        }
    }, [params]);

    const handleLoadDisplay = displayId => {
        loadDisplayInfo(displayId);
    };

    const handleClearEffect = displayId => {
        clearDisplayEffect(displayId);
    };

    const handleSetEffect = data => {
        setDisplayEffect(data.displayId, data);
    };

    const handleTypeChange = effectType => {
        getEffectPresets(effectType);
    };

    const { display, effect, isDisplayLoading } = selectedDisplay;

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
                                onClear={handleClearEffect}
                                onSubmit={handleSetEffect}
                                onTypeChange={this.handleTypeChange}
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
                            activatePreset={activatePreset}
                            getEffectPresets={getEffectPresets}
                            addPreset={addPreset}
                        />
                    )}
                </Grid>
                {/* {parseInt(window.localStorage.getItem('BladeMod')) > 2 && (
                    <Grid item xs={12} lg={6}>
                        <Card>
                            <CardContent>
                                <EffectControlBlade
                                    display={display}
                                    effect={effect}
                                    schemas={schemas}
                                    onClear={this.handleClearEffect}
                                    onSubmit={this.handleSetEffect}
                                    onTypeChange={this.handleTypeChange}
                                />
                            </CardContent>
                        </Card>
                    </Grid>
                )} */}
                {parseInt(window.localStorage.getItem('BladeMod')) > 1 && <>
                <Grid item xs={6} lg={6}>
                    <Card>
                        <CardContent>
                            <Typography variant="h5">Display Config</Typography>
                            <Typography variant="subtitle1">
                                Total Pixels: {display.config[display.id].pixel_count}
                            </Typography>
                            <br />
                            <Typography variant="caption">
                                Active: {JSON.stringify(display.config[display.id].active)}
                                <br />
                                Center Offset: {display.config[display.id].config.center_offset}
                                <br />
                                Crossfade: {display.config[display.id].config.crossfade}
                                <br />
                                Max Brightness: {display.config[display.id].config.crossfade}
                                <br />
                                Preview only:{' '}
                                {JSON.stringify(display.config[display.id].config.preview_only)}
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid item xs={6} lg={6}>
                    <Card>
                        <CardContent>
                            <Typography variant="h5">Display Segments</Typography>
                            <Typography variant="subtitle1">
                                Segments: {display.config[display.id].segments.length}
                            </Typography>
                            <br />
                            {display.config[display.id].segments.map(
                                (s, i) => <li key={i}>{s.join(',')}</li>
                            )}
                        </CardContent>
                    </Card>
                </Grid></>}
            </Grid>
        </>
    );
}

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

DisplayView.propTypes = {
    schemas: PropTypes.object.isRequired,
    selectedDisplay: PropTypes.object.isRequired,
};

export default connect(
    state => ({
        schemas: state.schemas,
        selectedDisplay: state.selectedDisplay,
        clearDisplayEffect: state.clearDisplayEffect,
        presets: state.presets,
    }),
    {
        loadDisplayInfo,
        clearDisplayEffect,
        setDisplayEffect,
        activatePreset,
        getEffectPresets,
        addPreset,
        fetchDisplayList,
    }
)(DisplayView);
