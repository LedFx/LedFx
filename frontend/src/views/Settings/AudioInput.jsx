import React from 'react';
import { makeStyles } from '@material-ui/core/styles';
import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
import MenuItem from '@material-ui/core/MenuItem';
import FormControl from '@material-ui/core/FormControl';
import Select from '@material-ui/core/Select';
import FormHelperText from '@material-ui/core/FormHelperText';
import Typography from '@material-ui/core/Typography';
import InputLabel from '@material-ui/core/InputLabel';

const useStyles = makeStyles({
    form: {
        display: 'flex',
    },
});

const AudioCard = ({ options, value, onChange, error, isSaving, isLoading }) => {
    const classes = useStyles();
    const handleAudioSelected = e => {
        const { value } = e.target;
        const selectedOption = options.find(o => o.value === value) || {};
        onChange(selectedOption);
    };

    return (
        <Card>
            <CardContent>
                <Typography variant="h6" color="textSecondary" gutterBottom>
                    Audio Input
                </Typography>
                <FormControl error={!!error} className={classes.form} disabled={isLoading || isSaving}>
                    <InputLabel id="audio-input-select-label">Current Device</InputLabel>
                    <Select
                        labelId="audio-input-select-label"
                        id="audio-input-select"
                        value={value}
                        onChange={handleAudioSelected}
                    >
                        {options.map(({ index, value }) => (
                            <MenuItem key={index} value={value}>
                                {value}
                            </MenuItem>
                        ))}
                    </Select>
                    <FormHelperText>{error}</FormHelperText>
                </FormControl>
            </CardContent>
        </Card>
    );
};

export default AudioCard;
