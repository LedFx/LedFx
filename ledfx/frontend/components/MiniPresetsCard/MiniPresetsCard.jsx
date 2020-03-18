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

  const renderPresetsButton = (presets, CATEGORY) => {
    if (!presets || !Object.keys(presets).length) return 'No presets defined in this category'
    return mapIncludeKey(presets).map(preset => {
        return (
          <Grid item key={preset.id}>
            <Button
              className={classes.presetButton}
              onClick={() => activatePreset(device.id, CATEGORY, device.effect.type, preset.id)}
            >
              {preset.name}
            </Button>
          </Grid>
        )
    })
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
              {renderPresetsButton(presets.defaultPresets, DEFAULT_CAT)}
            </Grid>
            <Grid item xs={6}>
              {renderPresetsButton(presets.customPresets, CUSTOM_CAT)}
            </Grid>
            <Grid item xs={12}>
              <AddPresetCard deviceId={device.id} presets={presets}></AddPresetCard>
            </Grid>
          </Grid>
        </CardContent>
      </Card>
    );
}

const mapStateToProps = state => ({ 
  presets: state.presets
})

const mapDispatchToProps = (dispatch) => ({
  activatePreset: (device, cat, effect, presetId) => dispatch(activatePreset(device, cat, effect, presetId)),
  getDevicePresets: (deviceId) => dispatch(getDevicePresets(deviceId))
})

export default connect(mapStateToProps, mapDispatchToProps)(MiniPresetsCard);