import React from 'react';
import PropTypes from 'prop-types';
import { SchemaForm, utils } from 'react-schema-form';
import clsx from 'clsx';
import withStyles from '@material-ui/core/styles/withStyles';
import Button from '@material-ui/core/Button';
import DialogActions from '@material-ui/core/DialogActions';
import Box from '@material-ui/core/Box';
import ExpandMoreIcon from '@material-ui/icons/ExpandMore';

import DropDown from 'components/forms/DropDown';
import AdditionalProperties from './AdditionalProperties';

const styles = theme => ({
    form: {
        display: 'flex',
        flexWrap: 'wrap',
    },
    schemaForm: {
        display: 'flex',
        flexWrap: 'wrap',
        width: '100%',
    },
    bottomContainer: {
        flex: 1,
        marginTop: 8,
    },
    actionButtons: {
        '& > *': {
            marginLeft: theme.spacing(2),
        },
    },
    expandIcon: {
        transform: 'rotate(180deg)',
    },
});

class SchemaFormCollection extends React.Component {
    constructor(props) {
        super(props);

        this.state = {
            collectionKey: '',
            model: {},
            additionalPropertiesOpen: false,
        };
    }

    componentDidMount() {
        const { selectedType, initial } = this.props;
        if (selectedType) {
            this.handleTypeChange(selectedType, initial);
        }
    }

    componentDidUpdate(nextProps) {
        const { selectedType, initial } = this.props;
        if (initial !== nextProps.initial || selectedType !== nextProps.selectedType) {
            console.log('are the initial values chnGING', nextProps.initial);
            this.handleTypeChange(nextProps.selectedType, nextProps.initial);
        }
    }

    handleTypeChange = (value, initial = {}) => {
        this.setState({ collectionKey: value, model: initial });
    };

    onModelChange = (key, val) => {
        utils.selectOrSet(key, this.state.model, val);
    };

    handleSubmit = e => {
        e.preventDefault();
        if (this.props.onSubmit) {
            this.props.onSubmit(this.state.collectionKey, this.state.model);
        }
    };

    toggleShowAdditional = e => {
        this.setState(prevState => ({
            additionalPropertiesOpen: !prevState.additionalPropertiesOpen,
        }));
    };

    render() {
        const {
            classes,
            schemaCollection,
            useAdditionalProperties,
            submitText,
            cancelText,
            onCancel,
        } = this.props;
        const { model, additionalPropertiesOpen, collectionKey } = this.state;

        const currentSchema = {
            type: 'object',
            title: 'Configuration',
            properties: {},
            ...(collectionKey ? schemaCollection[collectionKey].schema : {}),
        };

        const requiredKeys = currentSchema.required;
        const optionalKeys = Object.keys(currentSchema.properties).filter(
            key => requiredKeys && requiredKeys.indexOf(key) === -1
        );

        const showAdditionalUi = !!(useAdditionalProperties && optionalKeys.length);

        return (
            <form onSubmit={this.handleSubmit} className={classes.form}>
                <DropDown
                    label="Type"
                    value={collectionKey}
                    options={Object.keys(schemaCollection).map(key => ({
                        value: key,
                        display: key,
                    }))}
                    onChange={this.handleTypeChange}
                />

                <SchemaForm
                    className={classes.schemaForm}
                    schema={currentSchema}
                    form={requiredKeys}
                    model={model}
                    onModelChange={this.onModelChange}
                />

                {showAdditionalUi && (
                    <AdditionalProperties
                        schema={currentSchema}
                        form={optionalKeys}
                        model={model}
                        onChange={this.onModelChange}
                        open={additionalPropertiesOpen}
                    />
                )}

                <DialogActions className={classes.bottomContainer}>
                    {showAdditionalUi && (
                        <Button
                            size="medium"
                            className={classes.additionalButton}
                            onClick={this.toggleShowAdditional}
                        >
                            <ExpandMoreIcon
                                color="disabled"
                                className={clsx({ [classes.expandIcon]: additionalPropertiesOpen })}
                            />
                            {`Show ${!additionalPropertiesOpen ? 'More' : 'Less'}`}
                        </Button>
                    )}
                    <Box
                        flex={1}
                        display="flex"
                        justifyContent="flex-end"
                        className={classes.actionButtons}
                    >
                        <Button className={classes.button} onClick={onCancel} color="primary">
                            {cancelText || 'Cancel'}
                        </Button>
                        <Button
                            className={classes.button}
                            type="submit"
                            variant="contained"
                            color="primary"
                            disabled={!collectionKey}
                        >
                            {submitText || 'Submit'}
                        </Button>
                    </Box>
                </DialogActions>
            </form>
        );
    }
}

SchemaFormCollection.propTypes = {
    onSubmit: PropTypes.func.isRequired,
    classes: PropTypes.object,
    schemaCollection: PropTypes.object,
    selectedType: PropTypes.string,
};
SchemaFormCollection.defaultProps = {
    classes: '',
    schemaCollection: {},
    selectedType: '',
};

export default withStyles(styles)(SchemaFormCollection);
