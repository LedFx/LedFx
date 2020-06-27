import React, { useEffect, useState } from 'react';
import { makeStyles } from '@material-ui/core/styles';
import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
import CardActions from '@material-ui/core/CardActions';
import CardHeader from '@material-ui/core/CardHeader';
import Button from '@material-ui/core/Button';
import Grid from '@material-ui/core/Grid';
import Typography from '@material-ui/core/Typography';
import TextField from '@material-ui/core/TextField';

// CONSTANT device categories
export const DEFAULT_CAT = 'default_presets';
export const CUSTOM_CAT = 'custom_presets';

const useStyles = makeStyles(theme => ({
    presetButton: {
        size: 'large',
        margin: theme.spacing(1),
        textDecoration: 'none',
        '&,&:hover': {
            color: '#000000',
        },
    },
    content: {
        display: 'flex',
        flexDirection: 'column',
        width: '100%',
    },
    actions: {
        display: 'flex',
        flexDirection: 'row',
        padding: theme.spacing(1),
    },
    buttonGrid: {
        direction: 'row',
        justify: 'flex-start',
        alignItems: 'baseline',
    },
}));

const PresetsCard = ({ device, presets, activatePreset, getDevicePresets, addPreset }) => {
    const classes = useStyles();
    const [name, setName] = useState('');
    useEffect(() => {
        getDevicePresets(device.id);
    }, [device.id, getDevicePresets]);

    const handleActivatePreset = (deviceId, category, type, presetId) => () => {
        activatePreset(deviceId, category, type, presetId);
    };

    const renderPresetsButton = (list, CATEGORY) => {
        if (!list?.length)
            return (
                <Button className={classes.presetButton} disabled>
                    No Presets Found
                </Button>
            );
        return list.map(preset => {
            return (
                <Grid item key={preset.id}>
                    <Button
                        className={classes.presetButton}
                        onClick={handleActivatePreset(
                            device.id,
                            CATEGORY,
                            presets.effectType,
                            preset.id
                        )}
                    >
                        {preset.name}
                    </Button>
                </Grid>
            );
        });
    };

    return (
        <Card variant="outlined">
            <CardHeader title="Presets" subheader="Explore different effect configurations" />
            <CardContent className={classes.content}>
                <Typography variant="subtitle2">Default</Typography>
                <Grid container className={classes.buttonGrid}>
                    {renderPresetsButton(presets?.defaultPresets, DEFAULT_CAT)}
                </Grid>
                <Typography variant="subtitle2">Custom</Typography>
                <Grid container className={classes.buttonGrid}>
                    {renderPresetsButton(presets?.customPresets, CUSTOM_CAT)}
                </Grid>
                <Typography variant="subtitle2">Add Preset</Typography>
                <Typography variant="subtitle1" color="textSecondary">
                    Save this effect configuration as a preset
                </Typography>
            </CardContent>
            <CardActions className={classes.actions}>
                <TextField
                    error={validateTextInput(name, presets)}
                    id="presetNameInput"
                    label="Preset Name"
                    onChange={e => setName(e.target.value)}
                />
                <Button
                    className={classes.presetButton}
                    color="primary"
                    size="small"
                    aria-label="Save"
                    disabled={enableButton(name, presets)}
                    variant="contained"
                    onClick={() => addPreset(name, device.id)}
                >
                    Save
                </Button>
            </CardActions>
        </Card>
    );
};

const validateTextInput = (input, presets) => {
    if (!presets || !presets.customPresets || !presets.defaultPresets) return false;
    const used = Object.keys(presets.customPresets).concat(Object.keys(presets.defaultPresets));
    return used.includes(input);
};

const enableButton = (input, presets) => {
    if (!presets || !presets.customPresets || !presets.defaultPresets) return false;
    const used = Object.keys(presets.customPresets).concat(Object.keys(presets.defaultPresets));
    return used.includes(input) || input === '';
};

export default PresetsCard;
