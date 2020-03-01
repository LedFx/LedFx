import React, { useEffect } from 'react';
import PropTypes from 'prop-types';
import { connect } from 'react-redux'
import { makeStyles } from '@material-ui/core/styles';
import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
import CardHeader from '@material-ui/core/CardHeader';
import Button from '@material-ui/core/Button';

import { activatePreset, getPresets } from 'frontend/actions';
import { mapIncludeKey } from 'frontend/utils/helpers';

const useStyles = makeStyles(theme => ({ 
  button: {
    margin: theme.spacing.unit,
    float: "right"
  },
  submitControls: {
    margin: theme.spacing.unit,
    display: "flex",
    width: "100%"
  },
}))

const MiniPresetsCard = ({ presets, activatePreset, getPresets }) => {

  const classes = useStyles()
  useEffect(getPresets, [])
    
  if (!presets) {
    return
  }

  return (
      <Card>
        <CardHeader title="Presets">
           {/*link header to presets management page*/}
        </CardHeader>
        <CardContent className={classes.submitControls}>
        {/*Buttons to activate each preset*/}
        {
            mapIncludeKey(presets).map(preset => {
              return (
                <Button
                  key={preset.id}
                  className={classes.button}
                  color="primary"
                  size="small"
                  aria-label="Activate"
                  variant = "contained"
                  onClick={() => activatePreset(preset.id)}
                >
                  {preset.name}
                </Button>
              );
            })
        }
        </CardContent>
      </Card>
    );
}


const mapStateToProps = state => ({ 
  presets: state.presets 
})

const mapDispatchToProps = (dispatch) => ({
  activatePreset: (presetId) => dispatch(activatePreset(presetId)),
  getPresets: () => dispatch(getPresets())
})

export default connect(mapStateToProps, mapDispatchToProps)(MiniPresetsCard);