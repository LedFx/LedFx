import React from "react";
import PropTypes from "prop-types";
import withStyles from "@material-ui/core/styles/withStyles";

import Button from "@material-ui/core/Button";
import Collapse from "@material-ui/core/Collapse";

import CustomTextField from "frontend/components/SchemaForm/CustomTextField.jsx";
import CustomCheckbox from "frontend/components/SchemaForm/CustomCheckbox.jsx";

import { validateData } from "frontend/components/SchemaForm/Utils.jsx";

const styles = theme => ({
  flexWrap: {
    display: "flex",
    flexWrap: "wrap",
    width: "100%"
  },
  submitControls: {
    margin: theme.spacing.unit,
    display: "block",
    width: "100%"
  },
  button: {
    float: "right"
  },
  additionalWrapper: {
    display: "inline-grid"
  },
  additionalButton: {
    display: "block",
    width: "100%",
    float: "right"
  }
});

class SchemaForm extends React.Component {
  componentMapper = {
    number: CustomTextField,
    integer: CustomTextField,
    text: CustomTextField,
    string: CustomTextField,
    password: CustomTextField,
    boolean: CustomCheckbox,
    checkbox: CustomCheckbox
  };

  constructor(props) {
    super(props);

    this.state = {
      showAdditional: false,
      formData: {}
    };
  }

  validate = () => {};

  handleSubmit = event => {
    event.preventDefault();

    let result = validateData(this.state.formData, this.props.schema);
    if (result.valid && this.props.onSubmit) {
      this.props.onSubmit(this.state.formData);
    }
  };

  handleChange = (prop, value) => {
    const newState = this.state;
    if (newState.formData[prop] && value === undefined) {
      delete newState.formData[prop];
    } else {
      newState.formData[prop] = value;
    }

    this.setState(newState);
    if (this.props.onChange) {
      this.props.onChange(newState.formData);
    }
  };

  showAdditional = () => {
    this.setState(...this.state, {
      showAdditional: !this.state.showAdditional
    });
  };

  componentDidUpdate(prevProps) {
    if (this.props.schema !== prevProps.schema) {
      this.setState({});
    }
  }

  render() {
    const {
      classes,
      primaryFilter,
      primaryOnly,
      children,
      className,
      schema,
      ...otherProps
    } = this.props;
    let properties = schema.properties;
    if (schema.required) {
      schema.required.forEach(prop => {
        schema.properties[prop].required = true;
      });
    }

    let primaryKeys = Object.keys(properties);
    let additionalKeys = [];
    if (primaryFilter) {
      primaryKeys = Object.keys(properties).filter(key =>
        primaryFilter(properties[key])
      );
      additionalKeys = Object.keys(properties).filter(
        key => !primaryFilter(properties[key])
      );
    }

    let primaryControls = primaryKeys.map(key => {
      let prop = properties[key];
      let Input = this.componentMapper[prop.type];
      if (!Input) {
        console.log("Invalid property: ", prop);
        return;
      }

      return (
        <Input
          {...otherProps}
          key={key}
          id={key}
          schema={prop}
          onChange={this.handleChange}
        />
      );
    });

    let additionUi = undefined;
    if (!primaryOnly && additionalKeys.length > 0) {
      let additionalControls = additionalKeys.map(key => {
        let prop = properties[key];
        let Input = this.componentMapper[prop.type];
        if (!Input) {
          console.log("Invalid property: ", prop);
          return;
        }

        return (
          <Input
            {...otherProps}
            key={key}
            id={key}
            schema={prop}
            onChange={this.handleChange}
          />
        );
      });

      additionUi = (
        <div className={classes.additionalWrapper}>
          <Button
            size="small"
            className={classes.additionalButton}
            onClick={this.showAdditional}
          >
            Additional Configuration
          </Button>
          <Collapse in={this.state.showAdditional}>
            <div className={classes.flexWrap}>{additionalControls}</div>
          </Collapse>
        </div>
      );
    }

    return (
      <form
        onSubmit={this.handleSubmit}
        className={`${classes.flexWrap} ${className}`}
      >
        {primaryControls}

        {additionUi}

        <div className={classes.submitControls}>
          {children ? (
            children
          ) : (
            <Button type="submit" className={classes.button}>
              Submit
            </Button>
          )}
        </div>
      </form>
    );
  }
}

SchemaForm.propTypes = {
  onChange: PropTypes.func,
  classes: PropTypes.object.isRequired,
  schema: PropTypes.object.isRequired
};

export default withStyles(styles)(SchemaForm);
