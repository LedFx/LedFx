import React from "react";
import PropTypes from "prop-types";

import Grid from "@material-ui/core/Grid";
import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
import Typography from '@material-ui/core/Typography';

const baseStyle = theme => ({
    cardResponsive: {
        width: "100%",
        marginTop: theme.spacing.unit * 3,
        overflowX: "auto"
    },
})



class DashboardView extends React.Component {

  render() {
    const { classes } = this.props;
    return (
      <div>
        <Card>
            <CardContent>
              <Typography variant="display2" gutterBottom>
                Nothing here yet :(
              </Typography>
            </CardContent>
        </Card>
      </div>
    );
  }
}

export default DashboardView;
