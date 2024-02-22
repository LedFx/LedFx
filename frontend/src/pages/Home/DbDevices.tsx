import { useTheme, Stack, Chip } from '@mui/material'
import {
  DataGrid,
  GridColDef,
  GridEventListener,
  GridRenderCellParams
  // GridRenderCellParams,
} from '@mui/x-data-grid'
import { useNavigate } from 'react-router-dom'
import BladeFrame from '../../components/SchemaForm/components/BladeFrame'
import useStore from '../../store/useStore'
import BladeIcon from '../../components/Icons/BladeIcon/BladeIcon'
// import BladeIcon from '../../components/Icons/BladeIcon/BladeIcon';

const DbDevices = () => {
  const theme = useTheme()
  const navigate = useNavigate()
  const virtuals = useStore((state) => state.virtuals)

  const handleEvent: GridEventListener<'rowClick'> = (params) =>
    navigate(`/device/${params.row.id}`)

  const columns: GridColDef[] = [
    { field: 'id', headerName: 'ID', width: 70 },
    {
      field: 'icon_name',
      headerName: '',
      width: 50,
      renderCell: (params: GridRenderCellParams) => (
        <BladeIcon name={params.value} />
      )
    },
    {
      field: 'name',
      headerName: 'Name',
      width: 220

      // renderCell: (params: GridRenderCellParams<string>) => (
      //   <Link
      //     component={RouterLink}
      //     color="inherit"
      //     style={{ textDecoration: 'none' }}
      //     to={`/device/${params.row.id}`}
      //   >
      //     <Typography>{params.value}</Typography>
      //   </Link>
      // ),
    },
    {
      field: 'is_device',
      headerName: 'is_device',
      width: 100,
      renderCell: (params: GridRenderCellParams) => (
        <Chip label={params.row.is_device ? 'Device' : 'Virtual'} />
      )
    }
  ]

  const rows: any = Object.values(virtuals).map((v: any) => ({
    ...v,
    ...v.config
  }))

  return (
    <BladeFrame
      labelStyle={{
        background: theme.palette.background.default,
        color: theme.palette.primary.main
      }}
      style={{
        borderColor: theme.palette.primary.main,
        padding: 20,
        minWidth: 450
      }}
      title="Entities"
    >
      <Stack width="100%" height="100%">
        <DataGrid
          onRowClick={handleEvent}
          rowHeight={50}
          columns={columns}
          hideFooter
          // headerHeight={1}
          pageSizeOptions={[100]}
          disableRowSelectionOnClick
          rows={rows}
          initialState={{
            // pagination: {
            //   pageSize: 100,
            // },
            sorting: {
              sortModel: [{ field: 'name', sort: 'asc' }]
            },
            columns: {
              columnVisibilityModel: {
                id: false
              }
            }
          }}
          sx={{
            borderColor: 'transparent',
            '&.MuiDataGrid-root .MuiDataGrid-cell:focus-within': {
              outline: 'none !important'
            }
          }}
        />
      </Stack>
    </BladeFrame>
  )
}

export default DbDevices
