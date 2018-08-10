import React from "react";
import PropTypes from "prop-types";
import withStyles from "@material-ui/core/styles/withStyles";

import Select from "@material-ui/core/Select";
import InputLabel from "@material-ui/core/InputLabel";
import MenuItem from "@material-ui/core/MenuItem";
import FormControl from "@material-ui/core/FormControl";

import SchemaForm from "frontend/components/SchemaForm/SchemaForm.jsx";

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
    marginLeft: 2 * theme.spacing.unit
  }
});

class SchemaFormCollection extends React.Component {
  constructor(props) {
    super(props);

    this.state = {
      collectionKey: ""
    };
  }

  handleChangeSelectedCollection = event => {
    this.setState({ collectionKey: event.target.value });
    if (this.props.onChange) {
        this.props.onChange(event.target.value, {})
    }
  };

  handleFormChange = value => {
    if (this.props.onChange) {
        this.props.onChange(this.state.collectionKey, value)
    }
  };

  handleFormSubmit = value => {
    if (this.props.onSubmit) {
        this.props.onSubmit(this.state.collectionKey, value)
    }
  }

  render() {
    const { classes, onChange, onSubmit, schemaCollection, ...otherProps } = this.props;

    let currentSchema = {properties: {}}
    if (this.state.collectionKey !== "") {
      currentSchema = schemaCollection[this.state.collectionKey].schema
    }

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
      <div className={classes.form}>
        {customSelect}
        <SchemaForm
        key={this.state.collectionKey}
        schema={currentSchema}
        onChange={this.handleFormChange}
        onSubmit={this.handleFormSubmit}
        className={classes.schemaForm}
        {...otherProps}/>
      </div>
    );
  }
}

SchemaFormCollection.propTypes = {
  onChange: PropTypes.func,
  classes: PropTypes.object.isRequired,
  schemaCollection: PropTypes.object.isRequired
};

export default withStyles(styles)(SchemaFormCollection);
