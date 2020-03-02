import React from "react";
import PropTypes from "prop-types";
import withStyles from "@material-ui/core/styles/withStyles";
import { MuiThemeProvider } from "@material-ui/core/styles";

import Select from "@material-ui/core/Select";
import InputLabel from "@material-ui/core/InputLabel";
import MenuItem from "@material-ui/core/MenuItem";
import ListSubheader from '@material-ui/core/ListSubheader';
import FormControl from "@material-ui/core/FormControl";
import Input from '@material-ui/core/Input';

import Button from "@material-ui/core/Button";
import Collapse from "@material-ui/core/Collapse";
import { defaultTheme } from "frontend/layouts/Default/Default.jsx"
//import SchemaForm from "frontend/components/SchemaForm/SchemaForm.jsx";

import { selectOrSet } from "frontend/components/SchemaForm/Utils.jsx";

var { SchemaForm } = require('react-schema-form');

const styles = theme => ({
  form: {
    display: "flex",
    flexWrap: "wrap"
  },
  flexWrap: {
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
  additionalWrapper: {
    display: "inline-grid"
  },
  additionalButton: {
    display: "block",
    width: "100%",
    float: "right"
  }
});

class SchemaFormCollection extends React.Component {
  constructor(props) {
    super(props);

    this.state = {
      collectionKey: "",
      interRender : false,
      showAdditional: false,
      model: {},
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

  componentDidMount() {
    
  }
  
  showAdditional = () => {
    this.setState(...this.state, {
      showAdditional: !this.state.showAdditional
    });
  };


  handleChangeSelectedCollection = event => {
    this.state.interRender = true;
    this.setState({ collectionKey: event.target.value });
    if (this.props.onChange) {
        this.props.onChange(event.target.value, {})
    }
  };

  onModelChange = (key, val) => {
    selectOrSet(key, this.state.model, val);
  }

  handleSubmit = event => {
    event.preventDefault();
    if (this.props.onSubmit) {
      this.props.onSubmit(this.state.collectionKey, this.state.model)
    }
  }

  render() {
    const { children, classes, onChange, onSubmit, schemaCollection, currentEffect, useAdditionalProperties, ...otherProps } = this.props;
    
    if(currentEffect !== undefined  && currentEffect !== null && currentEffect.effect !== null && this.state.interRender == false)
    {
      if(currentEffect.effect.type === undefined)
        this.state.collectionKey = "";
      else
        this.state.collectionKey = currentEffect.effect.type;
      
      if(currentEffect.effect.config === undefined)
        this.state.model = {};
      else
        this.state.model = currentEffect.effect.config;
    }

    this.state.interRender = false;
    var currentSchema = {"type": "object", "title": "Effect Configuration", properties: {}}
    if (this.state.collectionKey !== "" ) {
      currentSchema = {...currentSchema, ...schemaCollection[this.state.collectionKey].schema};
    }

    let customSelect = (
      <FormControl className={classes.control}>
        <InputLabel>Type</InputLabel>
        <Select
          value={this.state.collectionKey}
          onChange={this.handleChangeSelectedCollection}
        >
          <MenuItem value="" select='selected'>
            <em>None</em>
          </MenuItem>
          
          {/* <ListSubheader>Test Subheader</ListSubheader> */}
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

    var additionUi = null
    var form = ["*"]
    const requiredKeys = currentSchema['required'];
    const optionalKeys = Object.keys(currentSchema['properties']).filter(
      key => requiredKeys && requiredKeys.indexOf(key) === -1);
    if (useAdditionalProperties && optionalKeys.length)
    {
      form = requiredKeys;
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
            <div className={classes.flexWrap} >
              <SchemaForm
                className={classes.schemaForm} 
                schema={currentSchema}
                form={optionalKeys}
                model={this.state.model}
                onModelChange={this.onModelChange}
                {...otherProps} />
            </div>
          </Collapse>
        </div>
      );
    }

    return (
      <form onSubmit={this.handleSubmit} className={classes.form}>
        {customSelect}

        <SchemaForm
          className={classes.schemaForm} 
          schema={currentSchema}
          form={form}
          model={this.state.model}
          onModelChange={this.onModelChange}
          {...otherProps} />
      
        {additionUi}
      
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
