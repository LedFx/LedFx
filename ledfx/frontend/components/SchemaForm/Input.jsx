import React from "react";
import {
  extractValue,
  validateValue
} from "frontend/components/SchemaForm/Utils.jsx";

export var ComposeInput = Input =>
  class extends React.Component {
    constructor(props) {
      super(props);
      let value = this.getDefaultValue(this.props);
      this.state = this.getUpdatedState(value);
      this.state.valid = true;
    }

    onChangeValidate = e => {
      let value = extractValue(e, this.props.schema);
      this.setState(this.getUpdatedState(value));

      if (this.props.onChange != undefined) {
        this.props.onChange(this.props.id, value);
      }
    };

    getUpdatedState = value => {
      let validationResult = validateValue(value, this.props.schema);
      return {
        value: value,
        valid: validationResult.valid,
        error: validationResult.valid ? null : validationResult.error.message
      };
    };

    getDefaultValue = props => {
      let value = undefined;
      if (props.schema["default"]) {
        value = props.schema["default"];
      }

      return value;
    };

    render() {
      return (
        <Input
          {...this.props}
          {...this.state}
          label = {this.props.schema.title ? this.props.schema.title : this.props.id}
          onChangeValidate={this.onChangeValidate}
        />
      );
    }
  };
