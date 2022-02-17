import React from 'react';
import Checkbox from '@material-ui/core/Checkbox';
import { FormGroup, FormControlLabel, makeStyles } from '@material-ui/core';

const useStyles = makeStyles(theme => ({
    root: {
        color: '#1ED760',
        '&$checked': {
            color: '#1ED760',
        },
    },
}));

export default function PitchSelect(props) {
    const pitchClasses = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
    const classes = useStyles();
    return (
        <FormGroup row="true">
            {pitchClasses.map(p => {
                return (
                    <FormControlLabel
                        control={
                            <Checkbox
                                color="primary"
                                className={classes.root}
                                checked={props.pitches[p]}
                                onClick={props.handleCheck}
                                name={p}
                            />
                        }
                        label={p}
                        style={{ color: '#1ED760' }}
                    />
                );
            })}
        </FormGroup>
    );
}
