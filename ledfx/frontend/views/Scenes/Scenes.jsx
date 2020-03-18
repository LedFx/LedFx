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

import ScenesCard from "frontend/components/SceneCard/SceneCard.jsx";
import ScenesConfigDialog from "frontend/components/SceneConfigDialog/SceneConfigDialog.jsx";
import AddSceneCard from "frontend/components/AddSceneCard/AddSceneCard";
import { getScenes } from 'frontend/actions';
import { includeKeyInObject } from 'frontend/utils/helpers';

const styles = theme => ({
  cardResponsive: {
    width: "100%",
    overflowX: "auto"
  },
  button: {
    position: "absolute",
    bottom: theme.spacing(2),
    right: theme.spacing(2)
  },
  dialogButton: {
    float: "right"
  }
});

class ScenesView extends React.Component {
  constructor(props) {
    super(props);
  }

  componentDidMount = () => {
    this.props.getScenes()
  }

  render() {
    const { classes } = this.props;
    return (
      <div>
        <Grid container direction="row" spacing={4}>
          <Grid item xs={12}>
            <AddSceneCard />
          </Grid>
          <React.Fragment>
            {renderScenes(this.props.scenes)}
          </React.Fragment>
        </Grid>
      </div>
    );
  }
}

const renderScenes = (scenes) => Object.keys(scenes).map((key) => (
  <Grid item xs={6}>
    <ScenesCard key={key} scene={includeKeyInObject(key, scenes[key])} />
  </Grid>
  ))


const mapStateToProps = state => ({ 
  scenes: state.scenes 
})

const mapDispatchToProps = (dispatch) => ({
  getScenes: () => dispatch(getScenes())
})

export default connect(mapStateToProps, mapDispatchToProps)(withStyles(styles)(ScenesView));