import { makeStyles } from '@material-ui/core/styles';
import { useState } from 'react';
import Slider from '@material-ui/core/Slider';
import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
import CardHeader from '@material-ui/core/CardHeader';
import Tooltip from '@material-ui/core/Tooltip';
import { TextField } from '@material-ui/core';

const log13 = x => Math.log(x) / Math.log(13);
const logIt = x => 3700.0 * log13(1 + x / 200.0);

const hzIt = x => 200.0 * 13 ** (x / 3700.0) - 200.0;

const useStyles = makeStyles(theme => ({
    content: {
        display: 'flex',
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        width: '100%',
        padding: theme.spacing(2),
        paddingBottom: 0,
    },
    formControl: {
        marginRight: theme.spacing(3),
    },
}));

const marks = [
    {
        value: 20,
        label: '20Hz',
    },
    {
        value: 250,
        label: '250Hz',
    },
    {
        value: 5000,
        label: '5000Hz',
    },
    {
        value: 10000,
        label: '10000Hz',
    },
    {
        value: 20000,
        label: '20000Hz',
    },
];
function ValueLabelComponent(props) {
    const { children, open, value } = props;

    return (
        <Tooltip
            open={open}
            enterTouchDelay={0}
            placement="top"
            title={`${Math.round(hzIt(value))} Hz`}
        >
            {children}
        </Tooltip>
    );
}
const MelbankSelector = () => {
    const [value, setValue] = useState([21, 20000]);

    const convertedMarks = marks.map(m => {
        return {
            value: logIt(m.value),
            label: m.label,
        };
    });

    const handleChange = (event, newValue) => {
        const copy = [...newValue];
        convertedMarks.forEach((m, i) => {
            if (Math.abs(newValue[0] - m.value) < 100) {
                copy[0] = m.value;
            }
            if (Math.abs(newValue[1] - m.value) < 100) {
                copy[1] = m.value;
            }
        });
        setValue(copy);
    };

    const convertedValue = [logIt(20), logIt(20000)];
    const classes = useStyles();

    return (
        <Card variant="outlined">
            <CardHeader title="Melbank Selector" subheader="Reactive frequency range" />
            <CardContent className={classes.content}>
                <div style={{ padding: '0 25px', width: '100%' }}>
                    <Slider
                        value={value}
                        aria-labelledby="discrete-slider-custom"
                        step={0.001}
                        valueLabelDisplay="auto"
                        marks={convertedMarks}
                        min={convertedValue[0]}
                        max={convertedValue[1]}
                        onChange={handleChange}
                        ValueLabelComponent={ValueLabelComponent}
                        onChangeCommitted={(e, val) => {
                            console.log(val);
                        }}
                    />
                    <div
                        style={{ width: '100%', display: 'flex', justifyContent: 'space-between' }}
                    >
                        <div style={{ maxWidth: '80px' }}>
                            <TextField
                                id="min"
                                label="Min"
                                type="number"
                                InputLabelProps={{
                                    shrink: true,
                                }}
                                value={Math.round(hzIt(value[0]))}
                                variant="outlined"
                                onChange={(e, n) => {
                                    setValue([logIt(e.target.value), value[1]]);
                                }}
                            />
                        </div>
                        <div>
                            <TextField
                                id="max"
                                label="Max"
                                type="number"
                                value={Math.round(hzIt(value[1]))}
                                onChange={(e, n) => {
                                    setValue([value[0], logIt(e.target.value)]);
                                }}
                                InputLabelProps={{
                                    shrink: true,
                                }}
                                variant="outlined"
                            />
                        </div>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
};
export default MelbankSelector;
