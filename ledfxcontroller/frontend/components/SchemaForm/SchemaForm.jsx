import React from "react";
import PropTypes from "prop-types";
import Button from "@material-ui/core/Button";
import TextField from "@material-ui/core/TextField";
import InputLabel from "@material-ui/core/InputLabel";
import FormControlLabel from "@material-ui/core/FormControlLabel";
import Checkbox from "@material-ui/core/Checkbox";
import FormControl from "@material-ui/core/FormControl";
import withStyles from "@material-ui/core/styles/withStyles";

const styles = theme => ({
  formControl: {
    margin: theme.spacing.unit,
    marginLeft: theme.spacing.unit * 2,
    minWidth: 300
  },
  textField: {
    marginLeft: theme.spacing.unit,
    marginRight: theme.spacing.unit
  },
  checkbox: {
    marginLeft: theme.spacing.unit,
    marginRight: theme.spacing.unit
  },
  button: {
    margin: theme.spacing.unit,
    float: 'right',
    display: 'inline-block'
  }
});

class SchemaForm extends React.Component {
  constructor(props) {
    super(props);
    this.state = {};
  }

  handleChange = name => event => {
    const { properties } = this.props;

    var val = event.target.value;
    if (properties[name].type === "boolean") {
      val = event.target.checked;
    } else if (properties[name].type === "integer") {
      val = parseInt(event.target.value);
    } else if (properties[name].type === "number") {
      val = parseFloat(event.target.value);
    }

    this.setState({ [name]: val });
  };

  handleSubmitForm = () => {
    this.props.onSubmit(this.state);
  };

  render() {
    const { classes, properties } = this.props;

    var checkboxControls = Object.keys(properties)
      .filter(key => properties[key].type === "boolean")
      .map((key, prop) => {
        return (
          <FormControl key={key} className={classes.formControl}>
            <FormControlLabel
              control={
                <Checkbox
                  onChange={this.handleChange(key)}
                  color="primary"
                  className={classes.checkbox}
                />
              }
              label={properties[key].title}
            />
          </FormControl>
        )
      });

    var inputControls = Object.keys(properties)
      .filter(key => properties[key].type !== "boolean")
      .map((key, prop) => {
        const isNumeric =
          properties[key].type === "integer" ||
          properties[key].type === "number";
        var defaultString = undefined
        if (properties[key].default != undefined) {
          var description = properties[key].description != undefined ? 
            properties[key].description + " " : ""
          defaultString = description + "(Default: " + properties[key].default + ")";
        }
        return (
          <FormControl key={key} className={classes.formControl}>
            <TextField
              onChange={this.handleChange(key)}
              label={properties[key].title}
              className={classes.textField}
              type={isNumeric ? "number" : "text"}
              helperText={defaultString}
              margin="dense"
            />
          </FormControl>
        )
      });

    return (
      <div>
        {inputControls}
        <br/>
        {checkboxControls}
        <br/>
        <Button
          variant="contained"
          color="primary"
          className={classes.button}
          onClick={this.handleSubmitForm}
        >{this.props.submitText}</Button>
      </div>
    );
  }
}

SchemaForm.defaultProps = {
  submitText: 'Submit'
};

SchemaForm.propTypes = {
  onSubmit: PropTypes.func.isRequired,
  submitText: PropTypes.string,
  classes: PropTypes.object.isRequired,
  properties: PropTypes.object.isRequired
};

export default withStyles(styles)(SchemaForm);
