import React from 'react';
import PropTypes from 'prop-types';
import withStyles from '@material-ui/core/styles/withStyles';
import Dialog from '@material-ui/core/Dialog';
import DialogContent from '@material-ui/core/DialogContent';
import DialogTitle from '@material-ui/core/DialogTitle';
import DialogContentText from '@material-ui/core/DialogContentText';

import SchemaFormCollection from 'components/SchemaForm';

const styles = theme => ({});

class DeviceConfigDialog extends React.Component {
    handleClose = () => {
        this.props.onClose();
    };

    handleSubmit = (type, config) => {
        const { initial, onAddDevice, onUpdateDevice } = this.props;

        console.log('what the submit stuffs', type, config, initial);
        if (initial.id) {
            onUpdateDevice(type, config);
        } else {
            onAddDevice(type, config);
        }

        this.props.onClose();
    };

    render() {
        const { classes, deviceTypes, open, initial } = this.props;
        return (
            <Dialog
                onClose={this.handleClose}
                className={classes.cardResponsive}
                aria-labelledby="form-dialog-title"
                disableBackdropClick
                open={open}
            >
                <DialogTitle id="form-dialog-title">Add Device</DialogTitle>
                <DialogContent className={classes.cardResponsive}>
                    <DialogContentText>
                        To add a device to LedFx, please first select the type of device you wish to
                        add then provide the necessary configuration.
                    </DialogContentText>
                    <SchemaFormCollection
                        schemaCollection={deviceTypes}
                        onSubmit={this.handleSubmit}
                        useAdditionalProperties={true}
                        onCancel={this.handleClose}
                        selectedType={initial.type}
                        initial={initial.config}
                    />
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
