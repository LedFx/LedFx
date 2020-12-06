import React, { useState } from 'react';
import { DragDropContext, Droppable, Draggable } from 'react-beautiful-dnd';
import DevicesTableItem from './DevicesTableItem';
import Table from '@material-ui/core/Table';
import TableBody from '@material-ui/core/TableBody';

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

    return (
        <DragDropContext onDragEnd={onDragEnd}>
            <Droppable droppableId="list">
                {provided => (
                    <div ref={provided.innerRef} {...provided.droppableProps}>
                        <QuoteList
                            quotes={state.quotes}
                            onEditDevice={onEditDevice}
                            onDeleteDevice={onDeleteDevice}
                            classes={classes}
                        />
                        {provided.placeholder}
                    </div>
                )}
            </Droppable>
        </DragDropContext>
    );
}
