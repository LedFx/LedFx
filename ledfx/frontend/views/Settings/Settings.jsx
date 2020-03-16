import React, { useState, useEffect } from "react";
import { connect } from "react-redux";

import { makeStyles } from '@material-ui/core/styles';
import Grid from "@material-ui/core/Grid";
import Card from "@material-ui/core/Card";
import CardHeader from "@material-ui/core/CardHeader";
import CardContent from "@material-ui/core/CardContent";
import InputLabel from '@material-ui/core/InputLabel';
import MenuItem from '@material-ui/core/MenuItem';
import FormHelperText from '@material-ui/core/FormHelperText';
import FormControl from '@material-ui/core/FormControl';
import Select from '@material-ui/core/Select';

import { getAudioDevices, setAudioDevice } from 'frontend/actions';

const useStyles = makeStyles(theme => ({
  root: {
    '& > *': {
      margin: theme.spacing(1),
    },
  },
}))

const SettingsView = ({ getAudioDevices, setAudioDevice, settings }) => {
  const classes = useStyles();
  
  useEffect(() => {
    getAudioDevices()
  }, [])

  const { audioDevices } = settings
  
  return (
    <div className={classes.root}>
      {audioDevices && (<AudioCard audioDevices={audioDevices} setAudioDevice={setAudioDevice} />)}
    </div>
    );
}

const AudioCard = ({ audioDevices, setAudioDevice }) => {
  const activeDeviceIndex = audioDevices['active_device_index']

  const [selectedIndex, setSelectedIndex] = useState(activeDeviceIndex)

  const handleAudioSelected = (index) => {
    setSelectedIndex(index)
    setAudioDevice(index)
  }

  return (<Card variant="outlined">
            <CardHeader title="Audio Device" subheader="Audio input for reactive effects. Sound card is better than microphone!" />
            <CardContent>
              <p>Current device: {audioDevices.devices[activeDeviceIndex]}</p>
              <FormControl>
                <Select
                  id="audio-input-select"
                  value={selectedIndex}
                  onChange={(e) => handleAudioSelected(e.target.value)}
                >
                {renderAudioInputSelect(audioDevices.devices)}
                </Select>
            </FormControl>
            </CardContent>
          </Card>
      )
}

const renderAudioInputSelect = (audioInputs) => {
  return Object.keys(audioInputs).map((key) => (<MenuItem
    key={key}
    value={key}
    >{audioInputs[key]}</MenuItem>))
}

const mapStateToProps = state => ({ 
  settings: state.settings 
})

const mapDispatchToProps = (dispatch) => ({
  getAudioDevices: () => dispatch(getAudioDevices()),
  setAudioDevice: (index) => dispatch(setAudioDevice(index))
})

export default connect(mapStateToProps, mapDispatchToProps)(SettingsView);
