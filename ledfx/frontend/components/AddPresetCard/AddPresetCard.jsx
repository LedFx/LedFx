import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { connect } from 'react-redux'
import { makeStyles } from '@material-ui/core/styles';

import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
import CardActions from '@material-ui/core/CardActions';
import TextField from '@material-ui/core/TextField';
import Button from '@material-ui/core/Button';

import { addPreset } from 'frontend/actions';

const useStyles = makeStyles({ 
  card: {
    display: "flex",
    direction: 'row',
    width: "100%",
    maxWidth: "100%",
    backgroundColor: "transparent",
    borderCollapse: "collapse",
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  form: {
    display: "flex",
    direction: 'row',
  },
  formItem: {
    alignSelf: 'center'
  }
});

const AddPresetCard = ({ presets, addPreset }) =>  {

  const [ name, setName ] = useState('')
  const classes = useStyles()

  return (
      <Card className={classes.card}>
        <CardContent>
          <h3>Add Preset</h3>
          <p>Save current effects of all devices as a preset</p>
        </CardContent>
        <CardActions>
          <div className = {classes.form}>
              <TextField
                className = {classes.formItem}
                error = {validateInput(name, presets)} 
                id="presetNameInput"
                label="Preset Name"
                onChange={(e) => setName(e.target.value)}
              />
              <Button
                className = {classes.formItem}
                color="primary"
                size="small"
                aria-label="Save"
                disabled = {validateInput(name, presets)} 
                variant = "contained"
                onClick = {() => addPreset(name)}
              >
                Save
              </Button> 
            </div>
        </CardActions>
      </Card>
    );
}

const validateInput = (input, presets) => (Object.keys(presets).includes(input) || input === "")

const mapStateToProps = state => ({ 
  presets: state.presets
})

const mapDispatchToProps = (dispatch) => ({
  addPreset: (presetName) => dispatch(addPreset(presetName))
})

export default connect(mapStateToProps, mapDispatchToProps)(AddPresetCard);