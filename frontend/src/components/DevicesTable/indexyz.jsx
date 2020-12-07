import React, { useState } from 'react';
import { DragDropContext, Droppable, Draggable } from 'react-beautiful-dnd';
import {
    List,
    ListItem,
    ListItemText,
    ListItemIcon,
    IconButton,
    ListItemSecondaryAction
} from "@material-ui/core";
import DevicesTableItem from './DevicesTableItemyz';
import Table from '@material-ui/core/Table';
import TableBody from '@material-ui/core/TableBody';
import RootRef from "@material-ui/core/RootRef";
import InboxIcon from "@material-ui/icons/Inbox";
import DeleteIcon from "@material-ui/icons/Delete";
import ReorderIcon from '@material-ui/icons/Reorder';
import Slider from '@material-ui/core/Slider';
const reorder = (list, startIndex, endIndex) => {
    const result = Array.from(list);
    const [removed] = result.splice(startIndex, 1);
    result.splice(endIndex, 0, removed);

    return result;
};

const Quote = ({ quote, index, onDeleteDevice, onEditDevice, classes }) => (
    <Draggable draggableId={quote.id} index={index}>
        {provided => (
            <div
                className={classes.tableResponsive}
                ref={provided.innerRef}
                {...provided.draggableProps}
                {...provided.dragHandleProps}
            >
                <Table className={classes.table}>
                    <TableBody>
                        <DevicesTableItem
                            index={index}
                            device={quote}
                            onDelete={onDeleteDevice}
                            onEdit={onEditDevice}
                            ref={provided.innerRef}
                            {...provided.draggableProps}
                            {...provided.dragHandleProps}
                        />
                    </TableBody>
                </Table>
            </div>
        )}
    </Draggable>
);

const QuoteList = React.memo(function QuoteList({ quotes, onDeleteDevice, onEditDevice, classes }) {
    return quotes.map((quote, index) => (
        <Quote
            quote={quote}
            index={index}
            key={quote.id}
            onDeleteDevice={onDeleteDevice}
            onEditDevice={onEditDevice}
            classes={classes}
        />
    ));
});

export default function QuoteApp({ onDeleteDevice, classes, items, onEditDevice }) {
    console.log("DAMN", items)
    const [state, setState] = useState({ quotes: items });
    function onDragEnd(result) {
        if (!result.destination) {
            return;
        }

        if (result.destination.index === result.source.index) {
            return;
        }

        const quotes = reorder(state.quotes, result.source.index, result.destination.index);

        setState({ quotes });
    }

    const reorder = (list, startIndex, endIndex) => {
        const result = Array.from(list);
        const [removed] = result.splice(startIndex, 1);
        result.splice(endIndex, 0, removed);

        return result;
    };
    const getItemStyle = (isDragging, draggableStyle) => ({
        // styles we need to apply on draggables
        ...draggableStyle,

        ...(isDragging && {
            background: "rgb(235,235,235)"
        })
    });

    const getListStyle = isDraggingOver => ({
        //background: isDraggingOver ? 'lightblue' : 'lightgrey',
    });
    const [value, setValue] = React.useState([1, 1]);

    const handleChange = (event, newValue) => {
        setValue(newValue);
    };

    return (
        <DragDropContext onDragEnd={onDragEnd}>
            <Droppable droppableId="list">
                {(provided, snapshot) => (
                    <RootRef rootRef={provided.innerRef}>
                        <List style={getListStyle(snapshot.isDraggingOver)}>
                            {items.map((item, index) => (
                                <Draggable key={item.id} draggableId={item.id} index={index} style={{ border: "2px solid red" }}>
                                    {(provided, snapshot) => (
                                        <ListItem
                                            ContainerComponent="li"
                                            ContainerProps={{ ref: provided.innerRef }}
                                            {...provided.draggableProps}
                                            {...provided.dragHandleProps}
                                            style={getItemStyle(
                                                snapshot.isDragging,
                                                provided.draggableProps.style
                                            )}
                                        >
                                            <ListItemIcon>
                                                <ReorderIcon />
                                            </ListItemIcon>
                                            <ListItemText
                                                primary={item.name}
                                                secondary={item.config.ip_address}
                                                style={{ flexBasis: "30%", flexGrow: 'unset', width: "30%" }}
                                            />
                                            <ListItemText style={{ flexBasis: "30%", flexGrow: 'unset', width: "30%" }}>

                                                <Slider
                                                    value={value}
                                                    marks={[
                                                        {
                                                            value: 1,
                                                            label: 1,
                                                        },
                                                        {
                                                            value: item.config.pixel_count,
                                                            label: item.config.pixel_count,
                                                        },
                                                    ]}
                                                    min={1}
                                                    max={item.config.pixel_count}
                                                    onChange={handleChange}
                                                    valueLabelDisplay="auto"
                                                    aria-labelledby="range-slider"
                                                />
                                            </ListItemText>

                                            <ListItemSecondaryAction>

                                                <IconButton>
                                                    <DeleteIcon />
                                                </IconButton>
                                            </ListItemSecondaryAction>
                                        </ListItem>
                                    )}
                                </Draggable>
                            ))}
                            {provided.placeholder}
                        </List>
                    </RootRef>
                )}
            </Droppable>
        </DragDropContext>
    );
}
