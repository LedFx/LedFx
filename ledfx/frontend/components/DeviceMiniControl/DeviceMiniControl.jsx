import React from "react";
import PropTypes from "prop-types";
import withStyles from "@material-ui/core/styles/withStyles";

import Card from "@material-ui/core/Card";
import CardContent from "@material-ui/core/CardContent";

const styles = theme => ({
  button: {
    margin: theme.spacing.unit,
    float: "right"
  }
});

class DeviceMiniControl extends React.Component {

  render() {
    const { classes, device } = this.props;
    console.log(device)
    return (
    <Card>
        <CardContent>
            {device.id}
        </CardContent>
    </Card>
    );
  }

}

DeviceMiniControl.propTypes = {
  classes: PropTypes.object.isRequired,
  device: PropTypes.object.isRequired
};

export default withStyles(styles)(DeviceMiniControl);
