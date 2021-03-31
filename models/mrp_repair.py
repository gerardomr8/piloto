from odoo import api, fields, models, _
from odoo.tools import float_compare


class Repair(models.Model):
    _inherit = 'mrp.repair'


    warranty_status = fields.Selection([('in_warranty', 'Under Warranty'), ('out_warranty', 'Out of Warranty')])
    need_part=fields.Boolean('Opt-out Part Change')
    state = fields.Selection([
        ('draft', 'Pending'),
        ('confirmed', 'Under Check'),
        ('under_repair', 'Under Repair'),
        ('waitingforpart', 'Waiting for Spare Part'),
        ('ready', 'Ready to Repair'),
        ('done', 'Closed'),
        ('2binvoiced', 'To be Invoiced'),
        ('invoice_except', 'Invoice Exception')], string='Status',track_visibility='onchange',
        copy=False, default='draft', readonly=True)

    @api.onchange('need_part')
    def onchange_partchange(self):
        if self.need_part:
            self.write({'state': 'waitingforpart'})
        else:
            self.write({'state': 'confirmed'})

    def action_validate(self):
        self.ensure_one()
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        available_qty_owner = self.env['stock.quant']._get_available_quantity(self.product_id, self.location_id, self.lot_id, owner_id=self.partner_id, strict=True)
        available_qty_noown = self.env['stock.quant']._get_available_quantity(self.product_id, self.location_id, self.lot_id, strict=True)
        for available_qty in [available_qty_owner, available_qty_noown]:
            if float_compare(available_qty, self.product_qty, precision_digits=precision) >= 0:
                return self.action_repair_confirm()
        else:
           self.action_incoming()
           self.action_repair_confirm()


    def action_incoming(self):
        stock_warehouse_id = self.env['stock.warehouse'].sudo().search([('company_id', '=', self.partner_id.company_id.id)])
        opearation_type_id = self.env['stock.picking.type'].sudo().search(
            [('code', '=', 'incoming'), ('warehouse_id', '=', stock_warehouse_id.id)])
        for picking_type_id in opearation_type_id:
            if (picking_type_id.warehouse_id.company_id == self.partner_id.company_id):
                picking_type_new_id = picking_type_id
        source_location= self.env['stock.location'].sudo().search([('usage', '=', 'Inventory Loss')]).id
        vals = {

            'partner_id': self.partner_id.id,
            'move_type': 'direct',
            'location_id': self.location_id.id,
            'location_dest_id': self.location_dest_id.id,
            'picking_type_id':picking_type_new_id.id
        }
        stock_picking_id = self.env['stock.picking'].sudo().create(vals)
        if stock_picking_id:
            line_vals = {
                'name': self.product_id.name,
                'picking_id': stock_picking_id.id,
                'product_id': self.product_id.id,
                'product_uom': self.product_id.uom_id.id,
                'product_uom_qty': self.product_qty,
                'location_id': self.location_dest_id.id,
                'location_dest_id': self.location_dest_id.id,
                'reserved_availability': self.product_qty,
                'state': 'done',
                'lot_id': self.lot_id.id,
                'lot_name': self.lot_id.name,
            }
            stock_move_id = self.env['stock.move'].sudo().create(line_vals)
            if stock_move_id:
                move_vals = {
                    'qty_done': self.product_qty,
                    'location_id': self.location_dest_id.id,
                    'location_dest_id': self.location_dest_id.id,
                    'picking_id': stock_picking_id.id,
                    'product_uom_id': self.product_id.uom_id.id,
                    'product_id': self.product_id.id,
                    'state': 'done',
                    'move_id': stock_move_id.id,
                    'lot_id': self.lot_id.id,
                    'lot_name': self.lot_id.name,
                }
                self.env['stock.move.line'].sudo().create(move_vals)