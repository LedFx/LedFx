import React from 'react';
import Typography from '@material-ui/core/Typography';
import Button from '@material-ui/core/Button';
import { makeStyles } from '@material-ui/core/styles';
import PixelSlider from './PixelSlider';
import { useSelector, useDispatch } from 'react-redux';
import PopoverSure from 'components/PopoverSure';
import ExpandLess from '@material-ui/icons/ExpandLess';
import ExpandMore from '@material-ui/icons/ExpandMore';
import SwapHorizIcon from '@material-ui/icons/SwapHoriz';
import { handleSegmentChange, orderSegmentChange, deleteSegment } from 'modules/displays';

const useStyles = makeStyles(theme => ({
    segmentsWrapper: {
        display: 'flex',
        borderBottom: '1px dashed #aaa',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '0.5rem 0',
    },
    segmentsColOrder: {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
    },
    segmentsButtonUp: {
        borderTopRightRadius: 0,
        borderBottomRightRadius: 0,
        minWidth: '50px',
    },
    segmentsButtonDown: {
        borderTopLeftRadius: 0,
        borderBottomLeftRadius: 0,
        minWidth: '50px',
        marginRight: '1rem',
    },
    segmentsColPixelSlider: {
        flex: '0 1 70%',
    },
    segmentsColActions: {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
    },
    '@media (max-width: 600px)': {
        segmentsColPixelSlider: {
            order: 3,
            width: 'calc(100% - 2rem)',
            margin: '2rem auto 0 auto',
        },

        segmentsWrapper: {
            flexDirection: 'column',
            alignItems: 'flex-start',
        },
        segmentsColActions: {
            position: 'absolute',
            right: '1rem',
        },
    },
}));

const Segment = ({ s, i, display }) => {
    const devices = useSelector(state => state.devices.list);
    const title = devices.find(d => d.id === s[0])['name'];
    const classes = useStyles();

    const dispatch = useDispatch();
    const handleInvert = () => {
        dispatch(handleSegmentChange({ segIndex: i, displayId: display.id, invert: true }));
    };
    const reorder = direction => {
        dispatch(orderSegmentChange({ segIndex: i, displayId: display.id, order: direction }));
    };
    const handleDeleteSegment = direction => {
        dispatch(deleteSegment({ segIndex: i, displayId: display.id }));
    };

    return (
        <div style={{ padding: '0 1rem' }}>
            <div className={classes.segmentsWrapper}>
                <div className={classes.segmentsColOrder}>
                    <div style={{ display: 'flex' }}>
                        <div>
                            <Button
                                disabled={i === 0}
                                variant={'outlined'}
                                color={'inherit'}
                                onClick={() => reorder('UP')}
                                size={'small'}
                                className={classes.segmentsButtonUp}
                            >
                                <ExpandLess />
                            </Button>
                        </div>
                        <div>
                            <Button
                                disabled={i === display.segments.length - 1}
                                variant={'outlined'}
                                color={'inherit'}
                                onClick={() => reorder('DOWN')}
                                size={'small'}
                                className={classes.segmentsButtonDown}
                            >
                                <ExpandMore />
                            </Button>
                        </div>
                    </div>
                    <div style={{ minWidth: '120px' }}>
                        <Typography color="textSecondary">{title}</Typography>
                    </div>
                </div>
                <div className={classes.segmentsColPixelSlider}>
                    <PixelSlider s={s} i={i} display={display} />
                </div>
                <div className={classes.segmentsColActions}>
                    <div>
                        <Button
                            variant={s[3] ? 'contained' : 'outlined'}
                            color={s[3] ? 'primary' : 'default'}
                            endIcon={<SwapHorizIcon />}
                            onClick={handleInvert}
                            style={{ margin: '0 1rem 0 1.5rem' }}
                        >
                            Flip
                        </Button>
                    </div>
                    <PopoverSure
                        variant="outlined"
                        color="default"
                        onConfirm={handleDeleteSegment}
                        style={{ padding: '5px' }}
                    />
                </div>
            </div>
        </div>
    );
};

export default Segment;
