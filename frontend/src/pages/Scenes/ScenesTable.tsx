import * as React from 'react'
import Box from '@mui/material/Box'
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid'
import { CardMedia, Chip } from '@mui/material'
import BladeIcon from '../../components/Icons/BladeIcon/BladeIcon'

const sceneImage = (iconName: string) =>
  iconName && iconName.startsWith('image:') ? (
    <CardMedia
      image={iconName.split('image:')[1]}
      title="Contemplative Reptile"
      sx={{ width: '100%', height: '100%' }}
    />
  ) : (
    <BladeIcon scene name={iconName} />
  )

const columns: GridColDef[] = [
  { field: 'id', headerName: 'ID', width: 70 },
  {
    field: 'scene_image',
    headerName: 'Image',
    width: 150,
    renderCell: (params: GridRenderCellParams) =>
      sceneImage(params.value || 'Wallpaper')
  },
  {
    field: 'name',
    headerName: 'Name',
    width: 300,
    editable: true
  },
  {
    field: 'scene_tags',
    headerName: 'Tags',
    width: 200,
    editable: true,
    renderCell: (params: GridRenderCellParams) =>
      params?.value &&
      params.value
        .split(',')
        .map((t: string) => (
          <Chip label={t} key={t} sx={{ cursor: 'pointer' }} />
        ))
  },
  {
    field: 'actions',
    headerName: 'Actions'
  }
]

export default function ScenesTable({ scenes }: any) {
  return (
    <Box sx={{ height: 500, width: '100%', maxWidth: '960px', m: '0 auto' }}>
      <DataGrid
        rows={Object.values(scenes).map((v: any, i: number) => ({
          id: i + 1,
          ...v
        }))}
        rowHeight={100}
        columns={columns}
        pageSizeOptions={[5]}
        // rowsPerPageOptions={[5]}
        checkboxSelection
        disableRowSelectionOnClick
        // experimentalFeatures={{ newEditingApi: true }}
      />
    </Box>
  )
}
