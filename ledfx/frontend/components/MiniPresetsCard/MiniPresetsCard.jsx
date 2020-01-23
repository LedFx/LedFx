import React from 'react';
import PropTypes from 'prop-types';
import { connect } from 'react-redux'
import { withStyles } from '@material-ui/core/styles';
import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
import CardActions from '@material-ui/core/CardActions';
import Button from '@material-ui/core/Button';

import { activatePreset, getPresets } from 'frontend/actions';

const styles = theme => ({ 
  button: {
    margin: theme.spacing.unit,
    float: "right"
  },
  submitControls: {
    margin: theme.spacing.unit,
    display: "block",
    width: "100%"
  },
});

class MiniPresetsCard extends React.Component {

  render() {
    const { classes, preset, activatePreset } = this.props;

  componentDidMount = () => {
    this.props.getPresets()
  }

    return (
      <Card>
        <CardContent>
          <h3>Presets</h3>
          {/*link header to presets management page*/}
        </CardContent>
        {/*Buttons to activate each preset*/}
        <CardActions className={classes.submitControls}>
          {
            Object.keys(presets).map(key => {
              return (
                <Button
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
        </CardActions>
      </Card>
    );
  }
}

const mapStateToProps = state => ({ 
  presets: state.presets 
})

const mapDispatchToProps = (dispatch) => ({
  activatePreset: (presetId) => dispatch(activatePreset(presetId)),
  getPresets: () => dispatch(getPresets())
})

export default connect(mapStateToProps, mapDispatchToProps)(withStyles(styles)(MiniPresetsCard));