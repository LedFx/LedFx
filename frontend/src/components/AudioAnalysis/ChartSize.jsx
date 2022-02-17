import React from 'react';
import { makeStyles } from '@material-ui/core/styles';
import Grid from '@material-ui/core/Grid';
import Typography from '@material-ui/core/Typography';
import Slider from '@material-ui/core/Slider';

const useStyles = makeStyles({
    root: {
        maxWidth: 400,
    },
    input: {
        width: 120,
    },
});

export default function ChartSize(props) {
    const classes = useStyles();

    return (
        <div className={classes.root}>
            <Typography id="input-slider" gutterBottom color="primary">
                Zoom
            </Typography>
            <Grid container spacing={2} alignItems="center">
                <Grid item xs>
                    <Slider
                        value={props.value}
                        step={100}
                        max={20000}
                        min={300}
                        valueLabelDisplay="auto"
                        onChange={props.handleSizeSliderChange}
                        aria-labelledby="chart-size-slider"
                    />
                </Grid>
            </Grid>
        </div>
    );
}
