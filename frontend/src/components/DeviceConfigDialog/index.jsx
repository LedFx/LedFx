import React from 'react';
import PropTypes from 'prop-types';
import { SchemaForm, utils } from 'react-schema-form';
import clsx from 'clsx';
import withStyles from '@material-ui/core/styles/withStyles';
import Button from '@material-ui/core/Button';
import DialogActions from '@material-ui/core/DialogActions';
import Box from '@material-ui/core/Box';
import ExpandMoreIcon from '@material-ui/icons/ExpandMore';
import Dialog from '@material-ui/core/Dialog';
import DialogContent from '@material-ui/core/DialogContent';
import DialogTitle from '@material-ui/core/DialogTitle';
import DialogContentText from '@material-ui/core/DialogContentText';
// import mapper from "./mapper"
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

class DeviceConfigDialog extends React.Component {
    constructor(props) {
        super(props);

        this.state = {
            deviceType: '',
            model: {},
            additionalPropertiesOpen: false,
        };
    }

    componentDidMount() {
        const { initial } = this.props;
        if (initial.type) {
            this.handleTypeChange(initial.type, initial.config);
        }
    }

    componentDidUpdate(prevProps) {
        const { initial } = this.props;
        if (initial !== prevProps.initial) {
            this.handleTypeChange(initial.type, initial.config);
        }
    }

    handleTypeChange = (value, initial = {}) => {
        this.setState({ deviceType: value, model: initial });
    };

    onModelChange = (key, val) => {
        utils.selectOrSet(key, this.state.model, val);
    };

    toggleShowAdditional = e => {
        this.setState(prevState => ({
            additionalPropertiesOpen: !prevState.additionalPropertiesOpen,
        }));
    };

    handleCancel = () => {
        this.props.onClose();
    };

    handleSubmit = e => {
        const { initial, onAddDevice, onUpdateDevice } = this.props;
        const { deviceType, model: config } = this.state;

        e.preventDefault();
        if (initial.id) {
            onUpdateDevice(initial.id, deviceType, config);
        } else {
            onAddDevice(deviceType, config);
        }

        this.props.onClose();
        window.location.reload();
    };

    render() {
        const { classes, deviceTypes, open, initial } = this.props;
        const { model, additionalPropertiesOpen, deviceType } = this.state;

        const currentSchema = {
            type: 'object',
            title: 'Configuration',
            properties: {},
            ...(deviceType ? deviceTypes[deviceType].schema : {}),
        };
        let requiredKeys = [];
        let optionalKeys = [];
        if (initial.id) {
            requiredKeys =
                currentSchema.required && currentSchema.required.filter(k => k !== 'name');
            optionalKeys = Object.keys(currentSchema.properties)
                .filter(key => !(requiredKeys && requiredKeys.some(rk => key === rk)))
                .filter(k => k !== 'icon_name')
                .filter(k => k !== 'name');
        } else {
            requiredKeys = currentSchema.required;
            optionalKeys = Object.keys(currentSchema.properties).filter(
                key => !(requiredKeys && requiredKeys.some(rk => key === rk))
            );
        }

        const showAdditionalUi = optionalKeys.length > 0;

        return (
            <Dialog
                onClose={this.handleClose}
                className={classes.cardResponsive}
                aria-labelledby="form-dialog-title"
                disableBackdropClick
                open={open}
            >
                <DialogTitle id="form-dialog-title">
                    {initial.id ? 'Edit Device' : 'Add Device'}
                </DialogTitle>
                <DialogContent className={classes.cardResponsive}>
                    <DialogContentText>
                        {initial.id
                            ? ` Edit your device configuration.`
                            : ` To add a device to LedFx, please first select the type of device you wish to
                                add then provide the necessary configuration.`}
                    </DialogContentText>

                    <form onSubmit={this.handleSubmit} className={classes.form}>
                        <DropDown
                            label="Type"
                            value={deviceType}
                            options={Object.keys(deviceTypes).map(key => ({
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
                            // mapper={mapper}
                            onModelChange={this.onModelChange}
                        />

                        {showAdditionalUi && (
                            <>

                                <AdditionalProperties
                                    schema={currentSchema}
                                    form={optionalKeys}
                                    model={model}
                                    onChange={this.onModelChange}
                                    open={additionalPropertiesOpen}
                                />

                            </>
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
                                        className={clsx({
                                            [classes.expandIcon]: additionalPropertiesOpen,
                                        })}
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
                                <Button
                                    className={classes.button}
                                    onClick={this.handleCancel}
                                    color="primary"
                                >
                                    {'Cancel'}
                                </Button>
                                <Button
                                    className={classes.button}
                                    type="submit"
                                    variant="contained"
                                    color="primary"
                                    disabled={!deviceType}
                                >
                                    {'Submit'}
                                </Button>
                            </Box>
                        </DialogActions>
                    </form>
                </DialogContent>
            </Dialog>
        );
    }
}

export default withStyles(styles)(DeviceConfigDialog);

DeviceConfigDialog.propTypes = {
    deviceTypes: PropTypes.object,
};

DeviceConfigDialog.defaultProps = {
    deviceTypes: {},
};
