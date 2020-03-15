import React, { useEffect } from 'react';
import PropTypes from 'prop-types';
import { connect } from 'react-redux'
import { makeStyles } from '@material-ui/core/styles';
import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
import CardHeader from '@material-ui/core/CardHeader';
import Button from '@material-ui/core/Button';
import Grid from "@material-ui/core/Grid";

import { activatePreset, getDevicePresets, DEFAULT_CAT, CUSTOM_CAT } from 'frontend/actions';
import AddPresetCard from 'frontend/components/AddPresetCard/AddPresetCard';
import { mapIncludeKey } from 'frontend/utils/helpers';

const useStyles = makeStyles(theme => ({ 
  presetButton: {
    size: "large",
    margin: theme.spacing(1),
    textDecoration: "none",
    "&,&:hover": {
      color: "#000000"
    }
  },
  submitControls: {
    display: "flex",
    width: "100%"
  },
  buttonGrid: {
    direction: "row",
    justify: "flex-start",
    alignItems: "baseline",
  }
}))

const MiniPresetsCard = ({ device, presets, activatePreset, getDevicePresets }) => {

  const classes = useStyles()
  useEffect(() => getDevicePresets(device.id), [])

  const handleActivatePreset = (CAT) => {
    return (pId) => activatePreset(device.id, CAT, device.effect.type, pId)
  }

  return (
      <Card>
        <CardHeader title="Presets">
           {/*link header to presets management page*/}
        </CardHeader>
        <CardContent className={classes.submitControls}>
          {/*Buttons to activate each preset*/}
          <Grid container className={classes.buttonGrid}>
            <Grid item xs={6}>
              {renderPresetsButton(presets.defaultPresets, classes.presetButton, handleActivatePreset(DEFAULT_CAT))}
            </Grid>
            <Grid item xs={6}>
              {renderPresetsButton(presets.customPresets, classes.presetButton, handleActivatePreset(CUSTOM_CAT))}
            </Grid>
            <Grid item xs={12}>
              <AddPresetCard deviceId={device.id} presets={presets}></AddPresetCard>
            </Grid>
          </Grid>
        </CardContent>
      </Card>
    );
}

const renderPresetsButton = (presets, classes, onActivate) => {
  if (!presets || !Object.keys(presets).length) return 'No presets defined in this category'
  return mapIncludeKey(presets).map(preset => {
      console.log(preset)
      return (
        <Grid item key={preset.id}>
          <Button
            className={classes}
            onClick={() => onActivate(preset.id)}
          >
            {preset.name}
          </Button>
        </Grid>
      );
  })
}

const mapStateToProps = state => ({ 
  presets: state.presets
})

const mapDispatchToProps = (dispatch) => ({
  activatePreset: (device, effect, presetId) => dispatch(activatePreset(device, effect, presetId)),
  getDevicePresets: (deviceId) => dispatch(getDevicePresets(deviceId))
})

export default connect(mapStateToProps, mapDispatchToProps)(MiniPresetsCard);