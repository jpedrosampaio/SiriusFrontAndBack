"""Financial operations keep Decimal through calculation and SQL persistence.

wire() is the HTTP/receipt serialization boundary; numeric JSON preserves the
existing frontend contract. Serialized numbers are never reused in calculations.
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID
from sqlalchemy import select, delete, update, func
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from db.models.finance import FinancialTransaction, Category, Budget, CreditCard, CardPurchase, Invoice, Projection, MonthlyBill
from db.repositories.finance import FinanceRepository, money
from services.time import local_today

DEFAULT_CATEGORIES = ['alimentação','transporte','moradia','saúde','educação','lazer','investimentos','salário','freelance','outros']
ZERO = Decimal('0.00')


def wire(value):
    return jsonable_encoder(value)


def month_date(value):
    try:
        parsed = date.fromisoformat(value+'-01')
        if parsed.strftime('%Y-%m') != value: raise ValueError()
        return parsed
    except (ValueError,TypeError):
        raise HTTPException(422,'Mês inválido; use YYYY-MM.') from None


def shift_month(value, offset):
    index = value.year*12+value.month-1+offset
    return date(index//12,index%12+1,1)


def public(row):
    names = {FinancialTransaction:'transaction_id', Category:'cat_id', Budget:'budget_id',CreditCard:'card_id',
        Invoice:'invoice_id',Projection:'projection_id',MonthlyBill:'bill_id'}
    data = {column.key:getattr(row,column.key) for column in row.__table__.columns}
    data[names[type(row)]] = data.pop('id')
    if 'month' in data: data['month'] = data['month'].strftime('%Y-%m')
    if isinstance(row,Projection): data['source_transaction_id'] = data.pop('purchase_id')
    return wire(data)


async def owned(session,model,user_id,identity):
    row = await session.scalar(select(model).where(model.user_id == user_id,model.id == identity))
    if row is None: raise HTTPException(404,'Registro não encontrado.')
    return row


async def projection_summary(session,user,month):
    rows = (await session.execute(select(Projection.category,Projection.is_fixed,Projection.projection_type,
        func.sum(Projection.amount),func.count()).where(Projection.user_id == user.id,Projection.month == month)
        .group_by(Projection.category,Projection.is_fixed,Projection.projection_type))).all()
    categories = {}; totals = {'fixed_expenses':ZERO,'installment_expenses':ZERO,'manual_expenses':ZERO}; count=0
    for category,fixed,kind,amount,n in rows:
        categories[category] = categories.get(category,ZERO)+amount
        totals['fixed_expenses' if fixed else 'installment_expenses' if kind=='installment' else 'manual_expenses'] += amount
        count += n
    income = (await FinanceRepository(session).period_totals(user.id,month,shift_month(month,1)))['income']
    total = sum(totals.values(),ZERO)
    return {'month':month.strftime('%Y-%m'),'total_projected_expenses':total,**totals,'categories_totals':categories,
        'estimated_income':income,'estimated_balance':income-total,'projections_count':count,
        'income_basis':'Receita registrada no próprio mês; sem repetição de salário passado.'}


async def preserve_paid_invoice(session,user,invoice):
    """Freeze explicit paid-flag coverage before adding a new charge; no ledger write."""
    rows=list((await session.scalars(select(Projection).where(Projection.user_id==user.id,
        Projection.card_id==invoice.card_id,Projection.month==invoice.month).limit(1001))).all())
    if len(rows)>1000:raise HTTPException(409,'Fatura excede o limite seguro de fontes; nenhuma compra foi aplicada.')
    bills=list((await session.scalars(select(MonthlyBill).where(MonthlyBill.user_id==user.id,
        MonthlyBill.card_id==invoice.card_id,MonthlyBill.month==invoice.month,
        (MonthlyBill.projection_id.is_not(None))|(MonthlyBill.source=='invoice_coverage')).limit(1001))).all())
    if len(bills)>1000:raise HTTPException(409,'Fatura excede o limite seguro de fontes; nenhuma compra foi aplicada.')
    by_projection={bill.projection_id:bill for bill in bills if bill.projection_id}
    for projection in rows:
        bill=by_projection.get(projection.id)
        if bill is None:
            bill=MonthlyBill(user_id=user.id,month=invoice.month,description=projection.description,amount=projection.amount,
                category=projection.category,card_id=invoice.card_id,projection_id=projection.id,source='projection')
            session.add(bill);bills.append(bill)
        bill.paid=True
    posted=await session.scalar(select(func.coalesce(func.sum(FinancialTransaction.amount),0))
        .join(CardPurchase,(CardPurchase.id==FinancialTransaction.purchase_id)&(CardPurchase.user_id==FinancialTransaction.user_id))
        .where(FinancialTransaction.user_id==user.id,FinancialTransaction.type=='expense',FinancialTransaction.bill_id.is_(None),
            CardPurchase.card_id==invoice.card_id,FinancialTransaction.date>=invoice.month,
            FinancialTransaction.date<shift_month(invoice.month,1)))
    residual=max(ZERO,invoice.amount-posted-sum((bill.amount for bill in bills),ZERO))
    if residual:
        session.add(MonthlyBill(user_id=user.id,month=invoice.month,description='Cobertura residual da fatura marcada paga',
            amount=residual,category='cartão',card_id=invoice.card_id,source='invoice_coverage',paid=True))
    invoice.paid=False


async def charge(session,user,card_id,args):
    card = await owned(session,CreditCard,user.id,card_id)
    amount = money(args['amount'])
    installments = max(2,args['installments'] or 1) if args['payment_type']=='parcelado' else 1
    cents = int(amount*100)
    if cents < installments: raise HTTPException(422,'Cada parcela deve ter pelo menos um centavo.')
    base,remainder = divmod(cents,installments)
    parts = [Decimal(base+(1 if i < remainder else 0))/100 for i in range(installments)]
    today = local_today(user.timezone)
    first = shift_month(today,1 if args['start_month']=='next' else 0)
    purchase = CardPurchase(user_id=user.id,card_id=card.id,amount=amount,description=args['description'] or '',
        category=args['category'],payment_type=args['payment_type'],installments=installments,
        first_month=first,start_month=args['start_month'])
    session.add(purchase); await session.flush()
    for index,part in enumerate(parts):
        month = shift_month(first,index)
        invoice = await session.scalar(select(Invoice).where(Invoice.user_id==user.id,Invoice.card_id==card.id,Invoice.month==month))
        if invoice and invoice.paid:await preserve_paid_invoice(session,user,invoice)
        description = f"{args['description'] or ''} (Cartão: {card.name})" + (f' - Parcela {index+1}/{installments}' if installments>1 else '')
        if index==0 and args['start_month']=='current':
            session.add(FinancialTransaction(id=purchase.id,user_id=user.id,type='expense',amount=part,
                category=args['category'],description=description,date=today,purchase_id=purchase.id))
        else:
            session.add(Projection(user_id=user.id,month=month,description=description,amount=part,
                category=args['category'],projection_type='installment',purchase_id=purchase.id,
                installment_number=index+1,total_installments=installments,card_id=card.id))
        if invoice: invoice.amount += part
        else: session.add(Invoice(user_id=user.id,card_id=card.id,month=month,amount=part))
    await session.flush()
    return wire({'message':'Charged to card','transaction_id':purchase.id,'installment_amount':parts[0],
        'total_amount':amount,'installments':installments})


async def create_projection(session,user,args):
    month = month_date(args['month'])
    count = 13 if args['is_fixed'] else (args['repeat_count'] or 1)
    first = None
    for index in range(count):
        row = Projection(user_id=user.id,month=shift_month(month,index),description=args['description'] or '',amount=money(args['amount']),
            category=args['category'],is_fixed=args['is_fixed'],repeat_count=args['repeat_count'],
            remaining_repeats=None if args['is_fixed'] else count-index,
            installment_number=index+1 if args['repeat_count'] else None,total_installments=args['repeat_count'])
        session.add(row)
        if first is None: first=row
    await session.flush()
    return public(first)


async def bills(session,user,month):
    # Preserve import-on-first-view behavior under the same user transaction lock.
    rows = list((await session.scalars(select(MonthlyBill).where(MonthlyBill.user_id==user.id,MonthlyBill.month==month)
        .order_by(MonthlyBill.created_at,MonthlyBill.id))).all())
    imported={row.projection_id for row in rows if row.projection_id}
    projections = (await session.scalars(select(Projection).where(Projection.user_id==user.id,Projection.month==month,
        Projection.id.not_in(imported)))).all()
    for row in projections:
        bill = MonthlyBill(user_id=user.id,month=month,description=row.description,amount=row.amount,category=row.category,
            source='projection',projection_id=row.id,card_id=row.card_id,
            installment_info=f'{row.installment_number}/{row.total_installments}' if row.installment_number else None)
        session.add(bill); rows.append(bill)
    await session.flush()
    rows=[row for row in rows if row.source!='deleted']
    total = sum((r.amount for r in rows),ZERO)
    paid = sum((r.amount for r in rows if r.paid),ZERO)
    return wire({'month':month.strftime('%Y-%m'),'bills':[public(r) for r in rows], 'total':total,
        'total_paid':paid,'total_pending':total-paid,'count':len(rows),'paid_count':sum(r.paid for r in rows)})


async def toggle_bill(session,user,bill_id,paid=None):
    bill = await owned(session,MonthlyBill,user.id,bill_id)
    if bill.source=='deleted':raise HTTPException(404,'Conta removida.')
    target = not bill.paid if paid is None else paid
    if target != bill.paid:
        bill.paid = target
        bill.paid_date = datetime.now(timezone.utc) if target else None
        if target:
            session.add(FinancialTransaction(user_id=user.id,type='expense',amount=bill.amount,category=bill.category,
                description=f'[Conta Paga] {bill.description}',date=local_today(user.timezone),bill_id=bill.id))
        else:
            await session.execute(delete(FinancialTransaction).where(FinancialTransaction.user_id==user.id,FinancialTransaction.bill_id==bill.id))
    await session.flush()
    return {'bill_id':str(bill.id),'paid':target,'message':'Conta marcada como paga!' if target else 'Pagamento desmarcado.'}


async def remove_projection(session,user_id,row):
    await session.execute(update(MonthlyBill).where(MonthlyBill.user_id==user_id,MonthlyBill.projection_id==row.id).values(projection_id=None))
    if row.card_id:
        invoice = await session.scalar(select(Invoice).where(Invoice.user_id==user_id,Invoice.card_id==row.card_id,Invoice.month==row.month))
        if invoice: invoice.amount = max(ZERO,invoice.amount-row.amount)
    await session.delete(row)
