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

    this.state = {
      addDialogOpened: false
    };
  }

  openAddDeviceDialog = () => {
    this.setState(...this.state, { addDialogOpened: true });
  };

  closeAddDeviceDialog = () => {
    this.setState(...this.state, { addDialogOpened: false });
  };

  render() {
    const { classes } = this.props;
    return (
      <div>
        <Table className={classes.table}>
          <TableBody>
            <Grid container direction="col" spacing={3}>
              {
                Object.keys(getPresets).map(id => { 
                  return (
                    <Grid item xs>
                      <PresetCard key={id} preset={getPresets[id]} />
                    </Grid>
                  );
                })
              }
            </Grid>
          </TableBody>
        </Table>
      </div>
    );
  }
}

export default withStyles(styles)(PresetsView);