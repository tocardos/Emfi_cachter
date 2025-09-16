from flask import Flask, render_template, request, redirect, url_for, flash,jsonify,session
import sqlite3
from datetime import datetime
from config import init_database,add_frequency_band,get_operator_frequencies

import tscm_logo 

app = Flask(__name__)
 # Change this in production
app.secret_key = "BigSecret"  # needed for sessions
init_database()
def get_db_connection():
    conn = sqlite3.connect('mobile_network.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    conn = get_db_connection()
    countries = conn.execute('SELECT * FROM countries').fetchall()
    operators = conn.execute('SELECT * FROM operators').fetchall()
    conn.close()
    return render_template('dbindex.html', countries=countries, operators=operators)

@app.route('/search', methods=['GET'])
def search():
    country = request.args.get('country')
    operator = request.args.get('operator')
    
    if not country or not operator:
        return redirect(url_for('dbindex'))
    
    conn = get_db_connection()
    results = conn.execute('''
        SELECT f.*, ocm.mnc, o.operator_name, c.country_name
        FROM frequency_bands f
        JOIN operator_frequency_mappings ofm ON f.id = ofm.frequency_band_id
        JOIN operator_country_mappings ocm ON ofm.operator_country_id = ocm.id
        JOIN operators o ON ocm.operator_id = o.id
        JOIN countries c ON ocm.mcc = c.mcc
        WHERE c.country_name = ? AND o.operator_name = ?
    ''', (country, operator)).fetchall()
    conn.close()
    
    return render_template('searchdb.html', results=results, 
                         country=country, operator=operator)

@app.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        conn = get_db_connection()
        try:
            # Add new frequency band
            cursor = conn.execute('''
                INSERT INTO frequency_bands (earfcn_arfcn, frequency_mhz, 
                                          bandwidth_mhz, technology)
                VALUES (?, ?, ?, ?)
            ''', (request.form['earfcn_arfcn'], 
                 float(request.form['frequency_mhz']),
                 float(request.form['bandwidth_mhz']),
                 request.form['technology']))
            
            # Get the operator_country_mapping ID
            mapping_id = conn.execute('''
                SELECT ocm.id FROM operator_country_mappings ocm
                JOIN operators o ON ocm.operator_id = o.id
                JOIN countries c ON ocm.mcc = c.mcc
                WHERE c.country_name = ? AND o.operator_name = ?
            ''', (request.form['country'], request.form['operator'])).fetchone()
            
            if mapping_id:
                conn.execute('''
                    INSERT INTO operator_frequency_mappings 
                    (operator_country_id, frequency_band_id, active_since, notes)
                    VALUES (?, ?, ?, ?)
                ''', (mapping_id[0], cursor.lastrowid, 
                     datetime.now().strftime('%Y-%m-%d'), 
                     request.form.get('notes', '')))
                
            conn.commit()
            flash('New frequency band added successfully!')
        except sqlite3.Error as e:
            flash(f'Error adding frequency band: {str(e)}')
        finally:
            conn.close()
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    countries = conn.execute('SELECT * FROM countries').fetchall()
    operators = conn.execute('SELECT * FROM operators').fetchall()
    conn.close()
    return render_template('adddb.html', countries=countries, operators=operators,mode='add')
@app.route('/add_country', methods=['POST'])
def add_country():
    country_name = request.form.get('country_name')
    country_code = request.form.get('country_code')
    print (f"country name {country_name}")
    conn = get_db_connection()
    # Check if country already exists
    existing_country =conn.execute('SELECT * FROM countries WHERE country_name=?',(country_name,)).fetchone()
    if existing_country:
        flash('Country already exists!', 'error')
        return redirect(url_for('index'))
    
    # Create new country
    #new_country = Country(country_name=country_name, country_code=country_code)
    
    try:
        cursor = conn.execute(
             "INSERT INTO countries (mcc, country_name) VALUES (?, ?)",
         (country_code, country_name))
        
        #db.session.add(new_country)
        #db.session.commit()
        conn.commit()
        flash('Country added successfully!', 'success')
    except Exception as e:
        #db.session.rollback()
        flash(f'Error adding country: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('index'))
@app.route('/add_operator', methods=['POST'])

def add_operator():
    operator_name = request.form.get('operator_name')
    country_name = request.form.get('country')
    mnc = request.form.get('operator_code')
    conn = get_db_connection()

    # Verify country exists
    #country = conn.execute('SELECT * FROM countries WHERE country_name=?',country_name).first()
    country = conn.execute('SELECT * FROM countries WHERE country_name=?',(country_name,)).fetchone()
    if not country:
        flash('Selected country does not exist!', 'error')
        conn.close()
        return redirect(url_for('index'))
    mcc = country['mcc']

    # Check if operator already exists
    #existing_operator = conn.execute('SELECT * FROM operators WHERE operator_name=?',operator_name).first()
    existing_operator = conn.execute('SELECT * FROM operators WHERE operator_name=?', (operator_name,)).fetchone()

    if existing_operator:
        flash('Operator already exists!', 'error')
        conn.close()
        return redirect(url_for('index'))
    conn.execute("INSERT INTO operators (operator_name) VALUES (?)", (operator_name,))
    conn.commit()
    operator = conn.execute('SELECT * FROM operators WHERE operator_name=?', (operator_name,)).fetchone()
    operator_id = operator['id']

    # Check if mcc + mnc combination already exists
    existing_mapping = conn.execute(
        'SELECT * FROM operator_country_mappings WHERE mcc=? AND mnc=?',
        (mcc, mnc)
    ).fetchone()
    if existing_mapping:
        flash(f'MNC {mnc} already exists in country {country_name} (MCC: {mcc})!', 'error')
        conn.close()
        return redirect(url_for('index'))
    
    
    
    # Create new operator
    #new_operator = Operator(operator_name=operator_name, country_name=country_name)
    
    try:
        conn.execute(
            "INSERT INTO operator_country_mappings (operator_id, mcc, mnc) VALUES (?, ?, ?)",
            (operator_id, mcc, mnc)
        )
        #conn.execute("INSERT INTO operators (operator_name) VALUES (?)",(operator_name,))
        #conn.execute("INSERT INTO operator_country_mappings (mnc) VALUE (?)",(mnc,))
        #db.session.add(new_operator)
        #db.session.commit()
        conn.commit()
        flash('Operator added successfully!', 'success')
    except Exception as e:
        #db.session.rollback()
        flash(f'Error adding operator: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('index'))

@app.route('/edit_band/<int:band_id>', methods=['GET', 'POST'])
def edit_band(band_id):
    conn = get_db_connection()
    band = conn.execute('''
        SELECT f.*, ocm.mnc, o.operator_name, c.country_name, ocm.mcc
        FROM frequency_bands f
        JOIN operator_frequency_mappings ofm ON f.id = ofm.frequency_band_id
        JOIN operator_country_mappings ocm ON ofm.operator_country_id = ocm.id
        JOIN operators o ON ocm.operator_id = o.id
        JOIN countries c ON ocm.mcc = c.mcc
        WHERE f.id = ?
    ''', (band_id,)).fetchone()

    if not band:
        flash("Frequency band not found!", "error")
        conn.close()
        return redirect(url_for('index'))

    countries = conn.execute('SELECT * FROM countries').fetchall()
    operators = conn.execute('SELECT * FROM operators').fetchall()

    if request.method == 'POST':
        try:
            conn.execute('''
                UPDATE frequency_bands
                SET earfcn_arfcn=?, frequency_mhz=?, bandwidth_mhz=?, technology=?
                WHERE id=?
            ''', (
                request.form['earfcn_arfcn'],
                float(request.form['frequency_mhz']),
                float(request.form['bandwidth_mhz']),
                request.form['technology'],
                band_id
            ))

            # also update the mapping (if country/operator changed)
            mapping_id = conn.execute('''
                SELECT ocm.id FROM operator_country_mappings ocm
                JOIN operators o ON ocm.operator_id = o.id
                JOIN countries c ON ocm.mcc = c.mcc
                WHERE c.country_name = ? AND o.operator_name = ?
            ''', (request.form['country'], request.form['operator'])).fetchone()

            if mapping_id:
                conn.execute('''
                    UPDATE operator_frequency_mappings
                    SET operator_country_id=?, notes=?
                    WHERE frequency_band_id=?
                ''', (
                    mapping_id[0],
                    request.form.get('notes', ''),
                    band_id
                ))

            conn.commit()
            flash("Frequency band updated successfully!", "success")
        except sqlite3.Error as e:
            flash(f"Error updating band: {str(e)}", "error")
        finally:
            conn.close()

        return redirect(url_for('index'))

    conn.close()
    #return render_template('edit_band.html', band=band,
    #                       countries=countries, operators=operators)
    return render_template('adddb.html',
                       countries=countries,
                       operators=operators,
                       mode="edit",
                       band=band)



if __name__ == '__main__':
    tscm_logo.cli()
    app.run(host='0.0.0.0',debug=True)
    