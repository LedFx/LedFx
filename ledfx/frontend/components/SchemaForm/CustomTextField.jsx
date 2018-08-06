import React from "react";
import PropTypes from "prop-types";
import withStyles from "@material-ui/core/styles/withStyles";
import TextField from "@material-ui/core/TextField";
import FormControl from "@material-ui/core/FormControl";
import { ComposeInput } from "frontend/components/SchemaForm/Input.jsx";

const styles = theme => ({
  control: {
    margin: theme.spacing.unit,
    minWidth: 250,
    flex: "1 0 30%"
  },
  textField: {}
});

class CustomTextField extends React.Component {
  constructor(props) {
    super(props);

    this.state = {
      lastSuccessfulValue: this.props.value ? this.props.value.toString() : ""
    };
  }

  componentWillReceiveProps(nextProps) {
    this.setState({
      lastSuccessfulValue: nextProps.value ? nextProps.value.toString() : ""
    });
  }

  render() {
    const { classes, onChangeValidate, schema, label, valid, error, ...otherProps } = this.props;

    return (
      <FormControl className={classes.control}>
        <TextField
          type={schema.type == "integer" ? "number" : schema.type}
          required={schema.required}
          label={label ? label : schema.title}
          helperText={valid ? schema.description : error}
          error={!valid}
          onChange={onChangeValidate}
          value={this.state.lastSuccessfulValue}
          disabled={schema.readonly}
          className={classes.textField}
          inputProps = {{
            step: schema.type == "number" ? 0.1 : undefined
          }}
        />
      </FormControl>
    );
  }
}

CustomTextField.propTypes = {
  schema: PropTypes.object.isRequired
};

export default ComposeInput(withStyles(styles)(CustomTextField));
