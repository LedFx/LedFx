import React from 'react';
import { useDispatch } from 'react-redux';
import {
    ListItem,
    ListItemText,
    ListItemIcon,
    ListItemSecondaryAction,
    Switch,
    TextField,
} from '@material-ui/core';
import { Draggable } from 'react-beautiful-dnd';
import FormatLineSpacingIcon from '@material-ui/icons/FormatLineSpacing';
import PixelSlider from './PixelSlider';
import PopoverSure from './PopoverSure';
import UsedPixels from './UsedPixels';

const DragDropItem = ({ listItem, virtual, index }) => {
    const dispatch = useDispatch();
    const onDeleteVitem = () => {
        dispatch({
            type: 'virtuals/DELETE_SEGMENT',
            payload: { virtual: virtual, device: listItem },
        });
    };

    const getItemStyle = (isDragging, draggableStyle) => ({
        // styles we need to apply on draggables
        ...draggableStyle,
        borderTop: '1px dashed grey',
        borderBottom: '1px dashed grey',
        ...(isDragging && {
            background: 'rgb(235,235,235)',
        }),
    });

    const handleInvert = (virtual, listItem) => {
        dispatch({
            type: 'virtuals/CHANGE_SEGMENT_INVERT',
            payload: { virtual: virtual, device: listItem },
        });
    };
    const handlePixelDensity = (virtual, listItem, newValue) => {
        dispatch({
            type: 'virtuals/CHANGE_SEGMENT_PIXELDENSITY',
            payload: { virtual: virtual, device: listItem, newValue: parseInt(newValue) },
        });
    };
    return (
        <Draggable
            key={`${listItem.id}-${index}`}
            draggableId={listItem.id}
            index={index}
            style={{ border: '2px solid red' }}
        >
            {(provided, snapshot) => (
                <ListItem
                    ContainerComponent="li"
                    ContainerProps={{ ref: provided.innerRef }}
                    {...provided.draggableProps}
                    style={getItemStyle(snapshot.isDragging, provided.draggableProps.style)}
                >
                    <ListItemIcon {...provided.dragHandleProps}>
                        <FormatLineSpacingIcon color="secondary" />
                    </ListItemIcon>
                    <ListItemText
                        primary={listItem.name}
                        secondary={listItem.config.ip_address}
                        style={{ flexBasis: '30%', flexGrow: 'unset', width: '30%' }}
                    />
                    <ListItemText style={{ flexBasis: '20%', flexGrow: 'unset', width: '20%' }}>
                        <PixelSlider virtual={virtual} device={listItem} />
                    </ListItemText>
                    <UsedPixels virtual={virtual} device={listItem} />
                    <ListItemText
                        primary={
                            <TextField
                                label=""
                                defaultValue={listItem.pixel_density || 30}
                                style={{
                                    minWidth: 'unset',
                                    maxWidth: '80%',
                                    margin: '0 1em 0 0',
                                    textAlign: 'center',
                                }}
                                inputProps={{ style: { textAlign: 'center' } }}
                                type="number"
                                onChange={e =>
                                    handlePixelDensity(virtual, listItem, e.target.value)
                                }
                            />
                        }
                        secondary={'PixelDensity'}
                        style={{
                            maxWidth: '10%',
                            textAlign: 'center',
                        }}
                    />
                    <ListItemText
                        primary={
                            <Switch
                                color="primary"
                                checked={listItem.invert}
                                onChange={() => handleInvert(virtual, listItem)}
                            />
                        }
                        secondary={'Invert'}
                        style={{ flexGrow: 0, textAlign: 'center' }}
                    />
                    <ListItemSecondaryAction>
                        <PopoverSure onDeleteVitem={onDeleteVitem} listItem={listItem} />
                    </ListItemSecondaryAction>
                </ListItem>
            )}
        </Draggable>
    );
};

export default DragDropItem;
