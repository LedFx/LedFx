import React from 'react';
import Typography from '@material-ui/core/Typography';
import Button from '@material-ui/core/Button';

import PixelSlider from './PixelSlider';
import { useSelector, useDispatch } from 'react-redux';
import { ButtonGroup, Switch } from '@material-ui/core';
import PopoverSure from 'components/PopoverSure';
import ExpandLess from '@material-ui/icons/ExpandLess';
import ExpandMore from '@material-ui/icons/ExpandMore';
import SwapHorizIcon from '@material-ui/icons/SwapHoriz';
import { handleSegmentChange } from 'modules/displays';
const Segment = ({ s, i, display }) => {
    const devices = useSelector(state => state.devices.list);
    const title = devices.find(d => d.id === s[0])['name'];
    // console.log(s, i, display, displays);

    const dispatch = useDispatch();
    const handleInvert = () => {
        dispatch(handleSegmentChange({ segIndex: i, displayId: display.id, invert: !s[3] }));
    };

    return (
        <div style={{ padding: '0 1rem' }}>
            <div
                style={{
                    display: 'flex',
                    borderBottom: '1px dashed #aaa',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '0.5rem 0',
                }}
            >
                <div>
                    <ButtonGroup style={{ paddingRight: '1rem' }}>
                        <Button
                            disabled={i === 0}
                            variant={'outlined'}
                            color={'inherit'}
                            onClick={() => console.log('BOOM')}
                            size={'small'}
                        >
                            <ExpandLess />
                        </Button>
                        <Button
                            disabled={i === display.segments.length - 1}
                            variant={'outlined'}
                            color={'inherit'}
                            onClick={() => console.log('BOOM')}
                            size={'small'}
                        >
                            <ExpandMore />
                        </Button>
                    </ButtonGroup>
                </div>
                <div style={{ flex: '0 0 30%', maxWidth: '200px' }}>
                    <Typography color="textSecondary">{title}</Typography>
                </div>
                <PixelSlider s={s} i={i} display={display} />
                <div style={{ width: '70px', paddingLeft: '2rem' }}>
                    <Button
                        variant={s[3] ? 'contained' : 'outlined'}
                        color={s[3] ? 'primary' : 'default'}
                        endIcon={<SwapHorizIcon />}
                        onClick={handleInvert}
                    >
                        Flip
                    </Button>
                </div>
                <div style={{ paddingLeft: '2rem' }}>
                    <PopoverSure variant="outlined" onConfirm={() => console.log('YO')} />
                </div>
            </div>
        </div>
    );
};

export default Segment;
