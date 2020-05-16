import React from "react";
import PropTypes from "prop-types";

import Grid from "@material-ui/core/Grid";
import Card from "@material-ui/core/Card";
import CardContent from "@material-ui/core/CardContent";

import MelbankGraph from "../../components/MelbankGraph/MelbankGraph.jsx";

class DeveloperView extends React.Component {

  componentDidMount() {
    const { device_id } = this.props.match.params;
  }

  render() {
    const { classes } = this.props;
    const { graphString } = this.props.match.params;

    let graphList = graphString.split("+")
    let graphDom = Object.keys(graphList).map(graphIndex => {
      return (
        <Grid item xs={12}>
          <p>{graphList[graphIndex].replace(/^\w/, c => c.toUpperCase())} Graph</p>
          <MelbankGraph key={graphIndex} graphId={graphList[graphIndex]}/>
        </Grid>
      );
    });

    return (
      <Grid container spacing={24}>
        {graphDom}
      </Grid>
    );
  }
}

export default DeveloperView;
