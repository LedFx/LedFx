import React from 'react';
import PropTypes from 'prop-types';
import { SchemaForm, utils } from 'react-schema-form';
import withStyles from '@material-ui/core/styles/withStyles';
import Typography from '@material-ui/core/Typography';
import Button from '@material-ui/core/Button';
import DialogActions from '@material-ui/core/DialogActions';
import Box from '@material-ui/core/Box';

import DropDown from 'components/forms/DropDown';

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

class EffectControl extends React.Component {
    constructor(props) {
        super(props);

        this.state = {
            selectedType: '',
            model: {},
        };
    }

    componentDidMount() {
        const { effect } = this.props;
        console.log('is there an effect on mount', effect);
        if (effect.type) {
            this.handleTypeChange(effect?.type, effect.config);
        }
    }

    componentDidUpdate(nextProps) {
        const { effect, initial } = this.props;
        if (
            effect?.type !== nextProps.effect?.type ||
            effect?.config !== nextProps.effect?.config
        ) {
            console.log('are the initial values chnGING', nextProps.effect);
            this.handleTypeChange(nextProps.effect.type, nextProps.effect.config);
        }
    }

    handleTypeChange = (value, initial = {}) => {
        console.log('whats the value and inital in handle change', value, initial);
        this.setState({ selectedType: value, model: initial });
    };

    onModelChange = (key, val) => {
        const model = utils.selectOrSet(key, this.state.model, val);
        console.log('whats this thingy here yo', model);
        this.setState({ model });
    };

    handleSubmit = e => {
        const { onSubmit, device } = this.props;
        const { selectedType, model } = this.state;

        e.preventDefault();
        if (onSubmit) {
            onSubmit({ deviceId: device.id, type: selectedType, config: model });
        }
    };

    handleRandomize = e => {
        const { onSubmit, device } = this.props;
        const { selectedType } = this.state;

        e.preventDefault();
        if (onSubmit) {
            onSubmit({ deviceId: device.id, type: selectedType, config: 'RANDOMIZE' });
        }
    };

    handleClearEffect = () => {
        const { onClear, device } = this.props;
        onClear(device.id);
    };

    render() {
        const { classes, schemas, effect } = this.props;
        const { model, selectedType } = this.state;

        const currentSchema = {
            type: 'object',
            title: 'Configuration',
            properties: {},
            ...(selectedType ? schemas.effects[selectedType].schema : {}),
        };

        const requiredKeys = Object.keys(currentSchema.properties);

        if (schemas.effects) {
            return (
                <>
                    <Typography variant="h5" color="inherit">
                        Effect Control
                    </Typography>
                    <form onSubmit={this.handleSubmit} className={classes.form}>
                        <DropDown
                            label="Type"
                            value={selectedType}
                            options={Object.keys(schemas?.effects).map(key => ({
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

                        <DialogActions className={classes.bottomContainer}>
                            <Button onClick={this.handleRandomize}>Randomize</Button>
                            <Box
                                flex={1}
                                display="flex"
                                justifyContent="flex-end"
                                className={classes.actionButtons}
                            >
                                <Button
                                    className={classes.button}
                                    onClick={this.handleClearEffect}
                                    color="primary"
                                >
                                    Clear Effect
                                </Button>
                                <Button
                                    className={classes.button}
                                    type="submit"
                                    variant="contained"
                                    color="primary"
                                    disabled={!selectedType}
                                >
                                    Set Effect
                                </Button>
                            </Box>
                        </DialogActions>
                    </form>
                </>
            );
        }

        return <p>Loading</p>;
    }
}

EffectControl.propTypes = {
    classes: PropTypes.object.isRequired,
    schemas: PropTypes.object.isRequired,
    device: PropTypes.object.isRequired,
    effect: PropTypes.object.isRequired,
};

export default withStyles(styles)(EffectControl);
