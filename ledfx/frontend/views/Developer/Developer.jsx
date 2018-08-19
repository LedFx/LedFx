import React from "react";
import PropTypes from "prop-types";

import Grid from "@material-ui/core/Grid";
import Card from "@material-ui/core/Card";
import CardContent from "@material-ui/core/CardContent";

import MelbankGraph from "frontend/components/MelbankGraph/MelbankGraph.jsx";

class DeveloperView extends React.Component {

  render() {
    const { classes } = this.props;
    return (
      <Grid container spacing={24}>
        <Grid item xs={12}>
          <p>Melbank Graph</p>
          <MelbankGraph/>
        </Grid>
      </Grid>
    );
  }
}

export default DeveloperView;
