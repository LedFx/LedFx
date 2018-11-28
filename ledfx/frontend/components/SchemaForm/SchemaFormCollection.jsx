import React from "react";
import PropTypes from "prop-types";
import withStyles from "@material-ui/core/styles/withStyles";
import { MuiThemeProvider } from "@material-ui/core/styles";

import Select from "@material-ui/core/Select";
import InputLabel from "@material-ui/core/InputLabel";
import MenuItem from "@material-ui/core/MenuItem";
import FormControl from "@material-ui/core/FormControl";

import Button from "@material-ui/core/Button";
import { defaultTheme } from "frontend/layouts/Default/Default.jsx"
//import SchemaForm from "frontend/components/SchemaForm/SchemaForm.jsx";

import { selectOrSet } from "frontend/components/SchemaForm/Utils.jsx";

var { SchemaForm } = require('react-schema-form');

const styles = theme => ({
  form: {
    display: "flex",
    flexWrap: "wrap"
  },
  control: {
    margin: theme.spacing.unit,
    width: '100%'
  },
  schemaForm: {
    marginLeft: 2 * theme.spacing.unit,
    marginRight: 2 * theme.spacing.unit,
    display: "flex",
    flexWrap: "wrap",
    width: "100%"
  },
});

class SchemaFormCollection extends React.Component {
  constructor(props) {
    super(props);

    this.state = {
      collectionKey: "",
      model: {
        test: "WHAT IS UP!"
      },
      form: [
        "*",
        {
          type: "submit",
          title: "Save"
        }
      ],
      action: [[
        {
          "category" : "user",
          "name" : "addAddress",
          "readOnly": false,
          "title" : "New"
        }
      ]]
    };
  }


  handleChangeSelectedCollection = event => {
    this.setState({ collectionKey: event.target.value });
    if (this.props.onChange) {
        this.props.onChange(event.target.value, {})
    }
  };

  onModelChange = (key, val) => {
    selectOrSet(key, this.state.model, val);
    console.log(this.state.model)
  }

  handleSubmit = event => {
    event.preventDefault();
    if (this.props.onSubmit) {
      this.props.onSubmit(this.state.collectionKey, this.state.model)
    }
  }

  render() {
    const { children, classes, onChange, onSubmit, schemaCollection, ...otherProps } = this.props;

    var currentSchema = {"type": "object", "title": "Effect Configuration", properties: {}}
    if (this.state.collectionKey !== "") {
      currentSchema = {...currentSchema, ...schemaCollection[this.state.collectionKey].schema}
    }

    console.log("SCHEMA", currentSchema)

    let customSelect = (
      <FormControl className={classes.control}>
        <InputLabel>Type</InputLabel>
        <Select
          value={this.state.collectionKey}
          onChange={this.handleChangeSelectedCollection}
        >
          <MenuItem value="">
            <em>None</em>
          </MenuItem>
          {Object.keys(schemaCollection).map(collectionKey => {
            return (
              <MenuItem key={collectionKey} value={collectionKey}>
                {collectionKey}
              </MenuItem>
            );
          })}
        </Select>
      </FormControl>
    );

    return (
      <form onSubmit={this.handleSubmit} className={classes.form}>
        {customSelect}

        <SchemaForm
          className={classes.schemaForm} 
          schema={currentSchema}
          form={this.state.form}
          model={this.state.model}
          onModelChange={this.onModelChange}
          {...otherProps} />
      
        {children ? (children) : (
          <Button type="submit" className={classes.button}>
            Submit
          </Button>
        )}
      
      </form>
    );
  }
}

SchemaFormCollection.propTypes = {
  onChange: PropTypes.func,
  classes: PropTypes.object.isRequired,
  schemaCollection: PropTypes.object.isRequired
};

export default withStyles(styles)(SchemaFormCollection);
