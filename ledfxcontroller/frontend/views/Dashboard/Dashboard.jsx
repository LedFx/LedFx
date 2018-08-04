import React from "react";
import PropTypes from "prop-types";

import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
import Typography from '@material-ui/core/Typography';

class DashboardView extends React.Component {

  render() {
    const { classes } = this.props;
    return (
      <div>
        <Card>
            <CardContent>
              <Typography variant="display2" gutterBottom>
                Nothing here yet, checkout the devices page!
              </Typography>
            </CardContent>
        </Card>
      </div>
    );
  }
}

export default DashboardView;
