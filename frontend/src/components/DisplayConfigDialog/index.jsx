import React from 'react';
// import PropTypes from 'prop-types';
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

// import DropDown from 'components/forms/DropDown';
import AdditionalProperties from './AdditionalProperties';
import { Link } from '@material-ui/core';

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

class DisplayConfigDialog extends React.Component {
    constructor(props) {
        super(props);

        this.state = {
            model: {},
            additionalPropertiesOpen: true,
        };
    }
    componentDidMount() {
        const { initial } = this.props;

        this.handleTypeChange(initial.config);
    }

    componentDidUpdate(prevProps) {
        const { initial } = this.props;
        if (initial !== prevProps.initial) {
            this.handleTypeChange(initial.config);
        }
    }
    handleTypeChange = (initial = {}) => {
        this.setState({ model: initial });
    };
    toggleShowAdditional = e => {
        this.setState(prevState => ({
            additionalPropertiesOpen: !prevState.additionalPropertiesOpen,
        }));
    };
    onModelChange = (key, val) => {
        utils.selectOrSet(key, this.state.model, val);
    };
    handleCancel = () => {
        this.props.onClose();
    };

    handleSubmit = () => {
        const { initial, onAddDisplay, onUpdateDisplay } = this.props;
        const { model: config } = this.state;
        console.log("Yz0001", initial, config)
        if (initial.id) {
            onUpdateDisplay(initial.id, { config });
        } else {
            onAddDisplay({ config });
        }
        // alert("NOT YET BROO")
        this.props.onClose();
    };

    render() {
        const { classes, open, displays, initial } = this.props;
        const { model, additionalPropertiesOpen } = this.state;

        const currentSchema = {
            type: 'object',
            title: 'Configuration',
            properties: {},
            ...(displays ? displays.schema : {}),
        };

        const requiredKeys = currentSchema.required;
        const optionalKeys = Object.keys(currentSchema.properties).filter(
            key => !(requiredKeys && requiredKeys.some(rk => key === rk))
        );
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
                    {initial.id ? 'Edit Device Settings' : 'Add Virtual Device'}
                </DialogTitle>
                <DialogContent className={classes.cardResponsive}>
                    <DialogContentText>
                        {initial.id
                            ? ` Inside Virtual-Devices, you can split devices into segments and merge
                             several segments over several devices into one VirtualDevice.`
                            : ` Inside Virtual-Devices, you can split devices into segments and merge
                             several segments over several devices into one VirtualDevice.`}
                    </DialogContentText>
                    <form onSubmit={this.handleSubmit} className={classes.form}>
                        <SchemaForm
                            className={classes.schemaForm}
                            schema={currentSchema}
                            form={requiredKeys}
                            model={model}
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
                                <DialogContentText>
                                    {additionalPropertiesOpen &&
                                        <div>
                                            *Available icons:
                                            <br />
                                            <Link href="https://material-ui.com/components/material-icons/">
                                                Material Icons,
                                            </Link>
                                            {' '}
                                            <Link href="https://materialdesignicons.com/">
                                                Material Design Icons
                                            </Link>
                                        </div>
                                    }
                                </DialogContentText>
                            </>
                        )}

                        <DialogActions className={classes.bottomContainer}>
                            <Box
                                flex={1}
                                display="flex"
                                justifyContent="flex-end"
                                className={classes.actionButtons}
                            >
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

export default withStyles(styles)(DisplayConfigDialog);
