import React from "react";
import PropTypes from "prop-types";
import withStyles from "@material-ui/core/styles/withStyles";
import Checkbox from "@material-ui/core/Checkbox";
import FormControl from "@material-ui/core/FormControl";
import FormControlLabel from "@material-ui/core/FormControlLabel";
import FormHelperText from "@material-ui/core/FormHelperText";
import Tooltip from "@material-ui/core/Tooltip";
import { ComposeInput } from "frontend/components/SchemaForm/Input.jsx";

const styles = theme => ({
  control: {
    margin: theme.spacing.unit,
    minWidth: 125,
    flex: "1 0 10%"
  },
  checkbox: {}
});

class CustomCheckbox extends React.Component {
  constructor(props) {
    super(props);

    this.state = {
      lastSuccessfulValue: this.props.value
    };
  }

  componentWillReceiveProps(nextProps) {
    this.setState({
      lastSuccessfulValue: nextProps.value
    });
  }

  render() {
    const {
      classes,
      schema,
      onChangeValidate,
      label,
      valid,
      error,
      ...otherProps
    } = this.props;

    return (
      <FormControl className={classes.control}>
        <FormControlLabel
          control={
            <Checkbox
                checked={this.state.lastSuccessfulValue}
                onChange={onChangeValidate}
                disabled={schema.readonly}
                className={classes.checkbox}
                />
          }
          label={label ? label : schema.title}
          title={schema.description}
        />
      </FormControl>
    );
  }
}

CustomCheckbox.propTypes = {
  schema: PropTypes.object.isRequired
};

export default ComposeInput(withStyles(styles)(CustomCheckbox));
