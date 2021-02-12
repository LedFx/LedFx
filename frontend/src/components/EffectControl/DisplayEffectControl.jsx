import React from 'react';
import PropTypes from 'prop-types';
import { SchemaForm, utils } from 'react-schema-form';
import withStyles from '@material-ui/core/styles/withStyles';
import Typography from '@material-ui/core/Typography';
import Button from '@material-ui/core/Button';
import DialogActions from '@material-ui/core/DialogActions';
import Box from '@material-ui/core/Box';

import CancelIcon from '@material-ui/icons/Cancel';
import CheckCircleIcon from '@material-ui/icons/CheckCircle';
import CasinoIcon from '@material-ui/icons/Casino';


import mapper from 'components/SchemaForm/mapper';
import BladeDropDown from './BladeDropDown';

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

class DisplayEffectControl extends React.Component {
    constructor(props) {
        super(props);

        this.state = {
            selectedType: '',
            model: {},
        };
    }

    componentDidMount() {
        const { effect } = this.props;
        if (effect.type) {
            this.handleTypeChange(effect?.type, effect.config);
        }
    }

    componentDidUpdate(prevProps) {
        const { effect } = this.props;
        if (effect.type !== prevProps.effect.type || effect?.config !== prevProps.effect?.config) {
            this.handleTypeChange(effect.type, effect.config);
        }
    }

    handleTypeChange = (value = '', initial = {}) => {
        const { onTypeChange } = this.props;
        this.setState({ selectedType: value, model: initial });
        if (onTypeChange) {
            onTypeChange(value);
        }
    };

    onModelChange = (key, val) => {
        const model = utils.selectOrSet(key, this.state.model, val);
        this.setState({ model });
    };

    handleSubmit = e => {
        const { onSubmit, display } = this.props;
        const { selectedType, model } = this.state;

        e.preventDefault();
        if (onSubmit) {
            onSubmit({ displayId: display.id, type: selectedType, config: model });
        }
    };

    handleRandomize = e => {
        const { onSubmit, display } = this.props;
        const { selectedType } = this.state;

        e.preventDefault();
        if (onSubmit) {
            onSubmit({ displayId: display.id, type: selectedType, config: 'RANDOMIZE' });
        }
    };

    handleClearEffect = () => {
        const { onClear, display } = this.props;
        onClear(display.id);
    };

    render() {
        const { classes, schemas } = this.props;
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
                    <Typography variant="h5">Effect Control</Typography>
                    <Typography variant="body1" color="textSecondary">
                        Set and configure effects
                    </Typography>
                    <form onSubmit={this.handleSubmit} className={classes.form}>
                        <BladeDropDown />
                        <SchemaForm
                            className={classes.schemaForm}
                            schema={currentSchema}
                            form={requiredKeys}
                            model={model}
                            onModelChange={this.onModelChange}
                            mapper={mapper}
                        />
                        <DialogActions className={classes.bottomContainer}>
                            {selectedType && (
                                <Button
                                    onClick={this.handleRandomize}
                                    endIcon={<CasinoIcon />}
                                    color="primary"
                                >
                                    Randomize
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
                                    onClick={this.handleClearEffect}
                                    color="primary"
                                    endIcon={<CancelIcon />}
                                >
                                    Clear Effect
                                </Button>
                                <Button
                                    className={classes.button}
                                    type="submit"
                                    variant="contained"
                                    color="primary"
                                    disabled={!selectedType}
                                    endIcon={<CheckCircleIcon />}
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

DisplayEffectControl.propTypes = {
    classes: PropTypes.object.isRequired,
    schemas: PropTypes.object.isRequired,
    display: PropTypes.object.isRequired,
    effect: PropTypes.object.isRequired,
};

export default withStyles(styles)(DisplayEffectControl);
