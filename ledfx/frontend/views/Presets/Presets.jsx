import React from "react";
import PropTypes from "prop-types";
import withStyles from "@material-ui/core/styles/withStyles";

import Typography from '@material-ui/core/Typography';
// import Slider from '@material-ui/core/Slider';
import Input from '@material-ui/core/Input';
import { connect } from "react-redux";

import Grid from "@material-ui/core/Grid";
import Card from "@material-ui/core/Card";
import CardContent from "@material-ui/core/CardContent";
import Button from "@material-ui/core/Button";
import AddIcon from "@material-ui/icons/Add";

import PresetsCard from "frontend/components/PresetCard/PresetCard.jsx";
import PresetsConfigDialog from "frontend/components/PresetConfigDialog/PresetConfigDialog.jsx";
import AddPresetCard from "frontend/components/AddPresetCard/AddPresetCard";
import { getPresets } from 'frontend/actions';

const styles = theme => ({
  cardResponsive: {
    width: "100%",
    overflowX: "auto"
  },
  button: {
    position: "absolute",
    bottom: theme.spacing.unit * 2,
    right: theme.spacing.unit * 2
  },
  dialogButton: {
    float: "right"
  }
});

class PresetsView extends React.Component {
  constructor(props) {
    super(props);
  }

  componentDidMount = () => {
    this.props.getPresets()
  }

  render() {
    const { classes } = this.props;
    return (
      <div>
        <AddPresetCard />
        <React.Fragment>
          {renderPresets(this.props.presets)}
        </React.Fragment>
      </div>
    );
  }
}

const renderPresets = (presets) => Object.keys(presets).map((key) => (<PresetsCard key={key} preset={transformPreset(key, presets[key])} />))

// Includes ID in preset
const transformPreset = (key, preset) => ({ id: key, ...preset})

const mapStateToProps = state => ({ 
  presets: state.presets 
})

const mapDispatchToProps = (dispatch) => ({
  getPresets: () => dispatch(getPresets())
})

export default connect(mapStateToProps, mapDispatchToProps)(withStyles(styles)(PresetsView));