import React from 'react';
import PropTypes from 'prop-types';
import { utils } from 'react-schema-form';
// import { SchemaForm, utils } from 'react-schema-form';
import withStyles from '@material-ui/core/styles/withStyles';
import Typography from '@material-ui/core/Typography';
import Grid from '@material-ui/core/Grid';
import { Slider, Switch } from '@material-ui/core';
import {
    WbSunny,
    BlurCircular,
    Flip,
    SwapHorizontalCircle,
    Palette,
    SignalCellular1BarRounded,
    Equalizer,
    Opacity,
    MergeType,
    AcUnit,
} from '@material-ui/icons';

const styles = theme => ({
    form: {
        display: 'flex',
        flexWrap: 'wrap',
    },
    schemaForm: {
        display: 'flex',
        flexWrap: 'wrap',
        width: '100%',
    },
    bottomContainer: {
        flex: 1,
        marginTop: 8,
    },
    actionButtons: {
        '& > *': {
            marginLeft: theme.spacing(2),
        },
    },
    expandIcon: {
        transform: 'rotate(180deg)',
    },
    colorsContainer: {
        display: 'flex',
        flexDirection: 'column',
        margin: '1rem 0 2rem 0',
    },
    colorContainer: {
        padding: '0.6rem 0.5rem 0.4rem',
        margin: '0.5rem 0',
        borderRadius: '0.5rem',
        justifyContent: 'space-around',
        alignItems: 'center',
        border: '1px solid #999',
        position: 'relative',
        boxSizing: 'border-box',
        display: 'flex',
        '& > label': {
            top: '-0.6rem',
            padding: '0 0.3rem',
            position: 'absolute',
            fontVariant: 'all-small-caps',
            backgroundColor: '#424242',
            boxSizing: 'border-box',
        },
        '& input[type="color"]': {
            width: '60px',
            height: '30px',
            padding: 0,
            borderRadius: '0.5rem',
        },
    },
    switchContainer: {
        borderRadius: '0.5rem',
        justifyContent: 'center',
        alignItems: 'center',
        border: '1px solid #999',
        position: 'relative',
        boxSizing: 'border-box',
        padding: '0.5rem 0.2rem 0.2rem 0.2rem',
        display: 'flex',
        '& > label': {
            top: '-0.6rem',
            padding: '0 0.3rem',
            position: 'absolute',
            fontVariant: 'all-small-caps',
            backgroundColor: '#424242',
            boxSizing: 'border-box',
        },
        '& > span': {
            margin: '0 0.3rem',
        },
    },
});

class EffectControl extends React.Component {
    constructor(props) {
        super(props);

        this.state = {
            selectedType: '',
            model: {},
        };
    }

    componentDidMount() {
        const { effect } = this.props;
        if (effect.type) {
            this.handleTypeChange(effect?.type, effect.config);
        }
    }

    componentDidUpdate(prevProps) {
        const { effect } = this.props;
        if (effect.type !== prevProps.effect.type || effect?.config !== prevProps.effect?.config) {
            this.handleTypeChange(effect.type, effect.config);
        }
    }

    handleTypeChange = (value = '', initial = {}) => {
        const { onTypeChange } = this.props;
        this.setState({ selectedType: value, model: initial });
        if (onTypeChange) {
            onTypeChange(value);
        }
    };

    onModelChange = (key, val) => {
        const model = utils.selectOrSet(key, this.state.model, val);
        this.setState({ model });
    };

    handleSubmit = e => {
        const { onSubmit, device } = this.props;
        const { selectedType, model } = this.state;

        e.preventDefault();
        if (onSubmit) {
            onSubmit({ deviceId: device.id, type: selectedType, config: model });
        }
    };

    handleRandomize = e => {
        const { onSubmit, device } = this.props;
        const { selectedType } = this.state;

        e.preventDefault();
        if (onSubmit) {
            onSubmit({ deviceId: device.id, type: selectedType, config: 'RANDOMIZE' });
        }
    };

    handleClearEffect = () => {
        const { onClear, device } = this.props;
        onClear(device.id);
    };

    render() {
        const { classes, schemas } = this.props;
        if (schemas.effects) {
            return (
                <>
                    <Typography variant="h5">Effect Control - Blade Mod</Typography>
                    <Typography variant="body1" color="textSecondary">
                        Set and configure effects
                    </Typography>
                    <div className={classes.colorsContainer}>
                        <div className={classes.colorContainer}>
                            <label>General</label>
                            <div className={classes.switchContainer}>
                                <label>Mirror</label>
                                <SwapHorizontalCircle />
                                <Switch color="primary" checked={true} />
                            </div>
                            <div className={classes.switchContainer}>
                                <label>Flip</label>
                                <Flip />
                                <Switch color="primary" />
                            </div>
                            <div className={classes.colorContainer} style={{ minWidth: '150px' }}>
                                <label>Brightness</label>
                                <Grid
                                    container
                                    style={{
                                        display: 'flex',
                                        justifyContent: 'center',
                                        alignItems: 'center',
                                    }}
                                    spacing={2}
                                >
                                    <Grid item>
                                        <WbSunny />
                                    </Grid>
                                    <Grid item xs style={{ paddingRight: '1.5rem' }}>
                                        <Slider
                                            aria-labelledby="discrete-slider"
                                            valueLabelDisplay="auto"
                                            marks
                                            step={0.1}
                                            min={0}
                                            max={1}
                                            defaultValue={1}
                                        />
                                    </Grid>
                                </Grid>
                            </div>
                            <div className={classes.colorContainer} style={{ minWidth: '150px' }}>
                                <label>Blur</label>
                                <Grid
                                    container
                                    style={{
                                        display: 'flex',
                                        justifyContent: 'center',
                                        alignItems: 'center',
                                    }}
                                    spacing={2}
                                >
                                    <Grid item>
                                        <BlurCircular />
                                    </Grid>
                                    <Grid item xs style={{ paddingRight: '1.5rem' }}>
                                        <Slider
                                            aria-labelledby="discrete-slider"
                                            valueLabelDisplay="auto"
                                            marks
                                            step={0.1}
                                            min={0}
                                            max={1}
                                            defaultValue={0}
                                        />
                                    </Grid>
                                </Grid>
                            </div>
                        </div>
                        <div className={classes.colorContainer}>
                            <label>LOWs</label>
                            <div className={classes.colorContainer}>
                                <label>Color</label>
                                <Grid
                                    container
                                    style={{
                                        display: 'flex',
                                        justifyContent: 'center',
                                        alignItems: 'center',
                                    }}
                                    spacing={2}
                                >
                                    <Grid item style={{ marginTop: '5px' }}>
                                        <Palette />
                                    </Grid>
                                    <Grid item xs style={{ paddingRight: '1rem' }}>
                                        <input type="color" defaultValue={'#ff0000'} />
                                    </Grid>
                                </Grid>
                            </div>
                            <div className={classes.colorContainer} style={{ minWidth: '210px' }}>
                                <label>Sensitivity</label>
                                <Grid
                                    container
                                    style={{
                                        display: 'flex',
                                        justifyContent: 'center',
                                        alignItems: 'center',
                                    }}
                                    spacing={2}
                                >
                                    <Grid item>
                                        <SignalCellular1BarRounded />
                                    </Grid>
                                    <Grid item xs style={{ paddingRight: '1.5rem' }}>
                                        <Slider
                                            aria-labelledby="discrete-slider"
                                            valueLabelDisplay="auto"
                                            marks
                                            step={0.01}
                                            min={0}
                                            max={0.3}
                                            defaultValue={0.03}
                                        />
                                    </Grid>
                                </Grid>
                            </div>
                            <div className={classes.colorContainer} style={{ minWidth: '210px' }}>
                                <label>Frequency</label>
                                <Grid
                                    container
                                    style={{
                                        display: 'flex',
                                        justifyContent: 'center',
                                        alignItems: 'center',
                                    }}
                                    spacing={2}
                                >
                                    <Grid item>
                                        <Equalizer />
                                    </Grid>
                                    <Grid item xs style={{ paddingRight: '1.5rem' }}>
                                        <Slider
                                            aria-labelledby="range-slider"
                                            valueLabelDisplay="auto"
                                            marks
                                            step={0.01}
                                            min={0}
                                            max={1}
                                            defaultValue={[0.3, 0.8]}
                                        />
                                    </Grid>
                                </Grid>
                            </div>
                        </div>
                        <div className={classes.colorContainer}>
                            <label>MIDs</label>
                            <div className={classes.colorContainer}>
                                <label>Color</label>
                                <Grid
                                    container
                                    style={{
                                        display: 'flex',
                                        justifyContent: 'center',
                                        alignItems: 'center',
                                    }}
                                    spacing={2}
                                >
                                    <Grid item style={{ marginTop: '5px' }}>
                                        <Palette />
                                    </Grid>
                                    <Grid item xs style={{ paddingRight: '1rem' }}>
                                        <input type="color" defaultValue={'#00ff00'} />
                                    </Grid>
                                </Grid>
                            </div>
                            <div className={classes.colorContainer} style={{ minWidth: '210px' }}>
                                <label>Sensitivity</label>
                                <Grid
                                    container
                                    style={{
                                        display: 'flex',
                                        justifyContent: 'center',
                                        alignItems: 'center',
                                    }}
                                    spacing={2}
                                >
                                    <Grid item>
                                        <SignalCellular1BarRounded />
                                    </Grid>
                                    <Grid item xs style={{ paddingRight: '1.5rem' }}>
                                        <Slider
                                            aria-labelledby="discrete-slider"
                                            valueLabelDisplay="auto"
                                            marks
                                            step={0.01}
                                            min={0}
                                            max={0.3}
                                            defaultValue={0.03}
                                        />
                                    </Grid>
                                </Grid>
                            </div>
                            <div className={classes.colorContainer} style={{ minWidth: '210px' }}>
                                <label>Frequency</label>
                                <Grid
                                    container
                                    style={{
                                        display: 'flex',
                                        justifyContent: 'center',
                                        alignItems: 'center',
                                    }}
                                    spacing={2}
                                >
                                    <Grid item>
                                        <Equalizer />
                                    </Grid>
                                    <Grid item xs style={{ paddingRight: '1.5rem' }}>
                                        <Slider
                                            aria-labelledby="range-slider"
                                            valueLabelDisplay="auto"
                                            marks
                                            step={0.01}
                                            min={0}
                                            max={1}
                                            defaultValue={[0.3, 0.8]}
                                        />
                                    </Grid>
                                </Grid>
                            </div>
                        </div>
                        <div className={classes.colorContainer}>
                            <label>Highs</label>
                            <div className={classes.colorContainer}>
                                <label>Color</label>
                                <Grid
                                    container
                                    style={{
                                        display: 'flex',
                                        justifyContent: 'center',
                                        alignItems: 'center',
                                    }}
                                    spacing={2}
                                >
                                    <Grid item style={{ marginTop: '5px' }}>
                                        <Palette />
                                    </Grid>
                                    <Grid item xs style={{ paddingRight: '1rem' }}>
                                        <input type="color" defaultValue={'#0000ff'} />
                                    </Grid>
                                </Grid>
                            </div>
                            <div className={classes.colorContainer} style={{ minWidth: '210px' }}>
                                <label>Sensitivity</label>
                                <Grid
                                    container
                                    style={{
                                        display: 'flex',
                                        justifyContent: 'center',
                                        alignItems: 'center',
                                    }}
                                    spacing={2}
                                >
                                    <Grid item>
                                        <SignalCellular1BarRounded />
                                    </Grid>
                                    <Grid item xs style={{ paddingRight: '1.5rem' }}>
                                        <Slider
                                            aria-labelledby="discrete-slider"
                                            valueLabelDisplay="auto"
                                            marks
                                            step={0.01}
                                            min={0}
                                            max={0.3}
                                            defaultValue={0.03}
                                        />
                                    </Grid>
                                </Grid>
                            </div>
                            <div className={classes.colorContainer} style={{ minWidth: '210px' }}>
                                <label>Frequency</label>
                                <Grid
                                    container
                                    style={{
                                        display: 'flex',
                                        justifyContent: 'center',
                                        alignItems: 'center',
                                    }}
                                    spacing={2}
                                >
                                    <Grid item>
                                        <Equalizer />
                                    </Grid>
                                    <Grid item xs style={{ paddingRight: '1.5rem' }}>
                                        <Slider
                                            aria-labelledby="range-slider"
                                            valueLabelDisplay="auto"
                                            marks
                                            step={0.01}
                                            min={0}
                                            max={1}
                                            defaultValue={[0.3, 0.8]}
                                        />
                                    </Grid>
                                </Grid>
                            </div>
                        </div>
                        <div className={classes.colorContainer}>
                            <label>Background</label>
                            <div className={classes.colorContainer}>
                                <label>Color</label>
                                <Grid
                                    container
                                    style={{
                                        display: 'flex',
                                        justifyContent: 'center',
                                        alignItems: 'center',
                                    }}
                                    spacing={2}
                                >
                                    <Grid item style={{ marginTop: '5px' }}>
                                        <Palette />
                                    </Grid>
                                    <Grid item xs style={{ paddingRight: '1rem' }}>
                                        <input type="color" defaultValue={'#000000'} />
                                    </Grid>
                                </Grid>
                            </div>
                            <div className={classes.colorContainer} style={{ minWidth: '210px' }}>
                                <label>Transparency</label>
                                <Grid
                                    container
                                    style={{
                                        display: 'flex',
                                        justifyContent: 'center',
                                        alignItems: 'center',
                                    }}
                                    spacing={2}
                                >
                                    <Grid item>
                                        <Opacity />
                                    </Grid>
                                    <Grid item xs style={{ paddingRight: '1.5rem' }}>
                                        <Slider
                                            aria-labelledby="discrete-slider"
                                            valueLabelDisplay="auto"
                                            marks
                                            step={0.1}
                                            min={0}
                                            max={1}
                                            defaultValue={0.5}
                                        />
                                    </Grid>
                                </Grid>
                            </div>
                            <div className={classes.switchContainer}>
                                <label>Mix BG</label>
                                <MergeType />
                                <Switch color="primary" />
                            </div>
                            <div className={classes.switchContainer}>
                                <label>Solid BG</label>
                                <AcUnit />
                                <Switch color="primary" />
                            </div>
                        </div>
                    </div>
                </>
            );
        }

        return <p>Loading</p>;
    }
}

EffectControl.propTypes = {
    classes: PropTypes.object.isRequired,
    schemas: PropTypes.object.isRequired,
    device: PropTypes.object.isRequired,
    effect: PropTypes.object.isRequired,
};

export default withStyles(styles)(EffectControl);
